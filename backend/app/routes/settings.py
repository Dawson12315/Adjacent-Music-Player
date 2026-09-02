from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.user import User
from app.schemas.database import DatabaseConnectionRequest
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.lastfm import get_lastfm_session, scrobble_track
from app.services.lastfm_enrichment_control import request_stop
from app.services.lastfm_enrichment_progress import get_progress, mark_stopping
from app.services.lastfm_enrichment_runner import (
    is_lastfm_enrichment_running,
    start_lastfm_enrichment_background,
)
from app.services.musicbrainz_backfill_runner import (
    is_musicbrainz_backfill_running,
    start_musicbrainz_backfill_background,
)
from app.services.scheduler import refresh_scheduler_jobs

router = APIRouter()


def settings_response(settings: AppSetting) -> dict:
    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
        "lastfm_api_key": settings.lastfm_api_key,
        "lastfm_api_secret_set": bool(settings.lastfm_api_secret),
        "lastfm_username": settings.lastfm_username,
        "lastfm_session_key_set": bool(settings.lastfm_session_key),
        "lastfm_enrichment_enabled": settings.lastfm_enrichment_enabled,
        "lastfm_enrichment_time": settings.lastfm_enrichment_time,
    }


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
        lastfm_enrichment_enabled=False,
        lastfm_enrichment_time=None,
    )

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


@router.get("/settings", response_model=AppSettingsResponse, tags=["settings"])
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    settings = get_or_create_settings(db)
    return settings_response(settings)


@router.put("/settings", response_model=AppSettingsResponse, tags=["settings"])
def update_settings(
    payload: AppSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    settings = get_or_create_settings(db)

    settings.cleanup_enabled = payload.cleanup_enabled
    settings.cleanup_time = payload.cleanup_time
    settings.scan_enabled = payload.scan_enabled
    settings.scan_time = payload.scan_time
    settings.lastfm_api_key = payload.lastfm_api_key
    settings.lastfm_username = payload.lastfm_username
    settings.lastfm_enrichment_enabled = payload.lastfm_enrichment_enabled
    settings.lastfm_enrichment_time = payload.lastfm_enrichment_time

    # Write-only secret: None means "keep", "" means "clear", anything else replaces.
    if payload.lastfm_api_secret is not None:
        settings.lastfm_api_secret = payload.lastfm_api_secret or None

    db.commit()
    db.refresh(settings)
    refresh_scheduler_jobs()

    return settings_response(settings)


@router.post("/settings/lastfm/enrich", tags=["settings"])
def trigger_lastfm_enrichment(
    current_user: User = Depends(require_admin),
):
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
def stop_lastfm_enrichment(
    current_user: User = Depends(require_admin),
):
    request_stop()
    mark_stopping()
    return {"status": "stopping"}


@router.get("/settings/lastfm/progress", tags=["settings"])
def get_lastfm_enrichment_progress(
    current_user: User = Depends(get_current_user),
):
    response = JSONResponse(content=get_progress())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/settings/lastfm/auth-url", tags=["settings"])
def get_lastfm_auth_url(
    callback_url: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    settings = get_or_create_settings(db)

    if not settings.lastfm_api_key:
        raise HTTPException(status_code=400, detail="Missing Last.fm API key")

    query = urlencode(
        {
            "api_key": settings.lastfm_api_key,
            "cb": callback_url,
        }
    )

    auth_url = f"https://www.last.fm/api/auth/?{query}"

    return {"auth_url": auth_url}


@router.post("/settings/lastfm/session", response_model=AppSettingsResponse, tags=["settings"])
def create_lastfm_session(
    token: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
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
        raise HTTPException(
            status_code=400,
            detail=result["error"] or "Failed to create Last.fm session",
        )

    settings.lastfm_session_key = result["session_key"]
    settings.lastfm_username = result["username"]

    db.commit()
    db.refresh(settings)

    return settings_response(settings)


@router.post("/settings/lastfm/test-scrobble", tags=["settings"])
def test_lastfm_scrobble(
    track: str,
    artist: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
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
def get_lastfm_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
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
        "musicbrainz_backfill_running": is_musicbrainz_backfill_running(),
        "musicbrainz_resume_available": tracks_missing_mbid > 0,
    }


@router.post("/settings/musicbrainz/resume", tags=["settings"])
def resume_musicbrainz_backfill(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    tracks_missing_mbid = (
        db.query(func.count(Track.id))
        .filter(Track.musicbrainz_recording_id.is_(None))
        .scalar()
        or 0
    )

    if tracks_missing_mbid == 0:
        return {
            "started": False,
            "reason": "nothing_to_resume",
        }

    if is_musicbrainz_backfill_running():
        return {
            "started": False,
            "reason": "already_running",
        }

    started = start_musicbrainz_backfill_background()

    return {
        "started": started,
        "reason": "started" if started else "already_running",
    }

# ---------------------------------------------------------------------------
# Database — multi-user status, Postgres connection testing, and the
# SQLite → Postgres migration. All admin-only.
# ---------------------------------------------------------------------------


@router.get("/settings/database", tags=["settings"])
def database_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from pathlib import Path

    from app.config import RUNTIME_DATABASE_CONFIG_PATH, settings as app_config
    from app.db import Base, engine
    from app.services.pg_migration import get_migration_progress, mask_database_url

    dialect = engine.dialect.name
    size_bytes = None
    migrated_at = None

    if dialect == "sqlite":
        raw_path = app_config.database_url.replace("sqlite:///", "", 1)
        db_file = Path(raw_path)
        if db_file.exists():
            size_bytes = db_file.stat().st_size

    if RUNTIME_DATABASE_CONFIG_PATH.exists():
        try:
            import json as json_module

            migrated_at = json_module.loads(
                RUNTIME_DATABASE_CONFIG_PATH.read_text(encoding="utf-8")
            ).get("migrated_at")
        except (OSError, ValueError):
            migrated_at = None

    from sqlalchemy import select as sa_select

    row_count = 0
    for table in Base.metadata.sorted_tables:
        row_count += (
            db.execute(sa_select(func.count()).select_from(table)).scalar() or 0
        )

    return {
        "engine": "postgresql" if dialect == "postgresql" else "sqlite",
        "multi_user": dialect == "postgresql",
        "url_masked": mask_database_url(app_config.database_url),
        "size_bytes": size_bytes,
        "row_count": row_count,
        "table_count": len(Base.metadata.sorted_tables),
        "migrated_at": migrated_at,
        "migration": get_migration_progress(),
    }


@router.post("/settings/database/test", tags=["settings"])
def test_database_connection(
    payload: DatabaseConnectionRequest,
    current_user: User = Depends(require_admin),
):
    from app.services.pg_migration import test_connection

    result = test_connection(payload)

    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/settings/database/migrate", status_code=202, tags=["settings"])
def start_database_migration(
    payload: DatabaseConnectionRequest,
    current_user: User = Depends(require_admin),
):
    from app.services.pg_migration import start_migration_background, test_connection

    # The UI gates on a successful test, but the API must not trust that.
    preflight = test_connection(payload)
    if not preflight["ok"]:
        raise HTTPException(status_code=400, detail=preflight["error"])

    result = start_migration_background(payload)

    if not result["started"]:
        if result["reason"] == "already_postgres":
            raise HTTPException(
                status_code=409, detail="This install already runs on PostgreSQL."
            )
        if result["reason"].startswith("job_running:"):
            job = result["reason"].split(":", 1)[1]
            raise HTTPException(
                status_code=409,
                detail=f"A background job is running ({job}). Wait for it to finish.",
            )
        raise HTTPException(status_code=409, detail="A migration is already running.")

    return {"started": True}


@router.get("/settings/database/migration", tags=["settings"])
def database_migration_progress(
    current_user: User = Depends(require_admin),
):
    from app.services.pg_migration import get_migration_progress

    return get_migration_progress()
