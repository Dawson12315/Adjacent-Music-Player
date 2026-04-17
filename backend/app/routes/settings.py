from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.lastfm import get_lastfm_session
from app.services.scheduler import refresh_scheduler_jobs
from app.services.lastfm import scrobble_track
from app.services.lastfm_enrichment_control import request_stop
from app.services.lastfm_enrichment_progress import get_progress, mark_stopping
from app.services.lastfm_enrichment_runner import (
    is_lastfm_enrichment_running,
    start_lastfm_enrichment_background,
)

router = APIRouter()


def get_or_create_settings(db: Session) -> AppSetting:
    settings = db.query(AppSetting).first()

    if settings:
        return settings

    settings = AppSetting(
        cleanup_enabled=False,
        cleanup_time=None,
        scan_enabled=False,
        scan_time=None,
        lastfm_api_key=None,
        lastfm_api_secret=None,
        lastfm_username=None,
        lastfm_session_key=None,
    )

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


@router.get("/settings", response_model=AppSettingsResponse, tags=["settings"])
def get_settings(db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)

    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
        "lastfm_api_key": settings.lastfm_api_key,
        "lastfm_api_secret": settings.lastfm_api_secret,
        "lastfm_username": settings.lastfm_username,
        "lastfm_session_key": settings.lastfm_session_key,
    }


@router.put("/settings", response_model=AppSettingsResponse, tags=["settings"])
def update_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)

    settings.cleanup_enabled = payload.cleanup_enabled
    settings.cleanup_time = payload.cleanup_time
    settings.scan_enabled = payload.scan_enabled
    settings.scan_time = payload.scan_time
    settings.lastfm_api_key = payload.lastfm_api_key
    settings.lastfm_api_secret = payload.lastfm_api_secret
    settings.lastfm_username = payload.lastfm_username
    settings.lastfm_session_key = payload.lastfm_session_key

    db.commit()
    db.refresh(settings)
    refresh_scheduler_jobs()

    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
        "lastfm_api_key": settings.lastfm_api_key,
        "lastfm_api_secret": settings.lastfm_api_secret,
        "lastfm_username": settings.lastfm_username,
        "lastfm_session_key": settings.lastfm_session_key,
    }


@router.post("/settings/lastfm/enrich", tags=["settings"])
def trigger_lastfm_enrichment():
    if is_lastfm_enrichment_running():
        return {
            "started": False,
            "reason": "already_running",
        }

    started = start_lastfm_enrichment_background()

    return {
        "started": started,
        "reason": "started" if started else "already_running",
    }


@router.post("/settings/lastfm/stop", tags=["settings"])
def stop_lastfm_enrichment():
    request_stop()
    mark_stopping()
    return {"status": "stopping"}


@router.get("/settings/lastfm/progress", tags=["settings"])
def get_lastfm_enrichment_progress():
    response = JSONResponse(content=get_progress())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.get("/settings/lastfm/auth-url", tags=["settings"])
def get_lastfm_auth_url(
    callback_url: str = Query(...),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db)

    if not settings.lastfm_api_key:
        return {"error": "missing_api_key"}

    auth_url = (
        "http://www.last.fm/api/auth/"
        f"?api_key={settings.lastfm_api_key}"
        f"&cb={callback_url}"
    )

    return {"auth_url": auth_url}

@router.post("/settings/lastfm/session", response_model=AppSettingsResponse, tags=["settings"])
def create_lastfm_session(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db)

    if not settings.lastfm_api_key or not settings.lastfm_api_secret:
        raise HTTPException(status_code=400, detail="Missing Last.fm API key or secret")

    result = get_lastfm_session(
        token=token,
        api_key=settings.lastfm_api_key,
        api_secret=settings.lastfm_api_secret,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Failed to create Last.fm session")

    settings.lastfm_session_key = result["session_key"]
    settings.lastfm_username = result["username"]

    db.commit()
    db.refresh(settings)

    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
        "lastfm_api_key": settings.lastfm_api_key,
        "lastfm_api_secret": settings.lastfm_api_secret,
        "lastfm_username": settings.lastfm_username,
        "lastfm_session_key": settings.lastfm_session_key,
    }

@router.post("/settings/lastfm/test-scrobble", tags=["settings"])
def test_lastfm_scrobble(
    track: str,
    artist: str,
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db)

    result = scrobble_track(
        api_key=settings.lastfm_api_key,
        api_secret=settings.lastfm_api_secret,
        session_key=settings.lastfm_session_key,
        track_name=track,
        artist_name=artist,
    )

    return result

@router.get("/settings/lastfm/readiness", tags=["settings"])
def get_lastfm_readiness(db: Session = Depends(get_db)):
    total_tracks = db.query(func.count(Track.id)).scalar() or 0

    tracks_missing_mbid = (
        db.query(func.count(Track.id))
        .filter(Track.musicbrainz_recording_id.is_(None))
        .scalar()
        or 0
    )

    tracks_with_mbid = total_tracks - tracks_missing_mbid

    progress_percent = 0
    if total_tracks > 0:
        progress_percent = round((tracks_with_mbid / total_tracks) * 100)

    ready = total_tracks > 0 and tracks_missing_mbid == 0

    return {
        "total_tracks": total_tracks,
        "tracks_with_mbid": tracks_with_mbid,
        "tracks_missing_mbid": tracks_missing_mbid,
        "progress_percent": progress_percent,
        "ready": ready,
    }