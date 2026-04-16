from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.app_setting import AppSetting
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.scheduler import refresh_scheduler_jobs
from app.services.lastfm_enrichment_batch import run_lastfm_enrichment
from app.services.lastfm_enrichment_control import request_stop
from app.services.lastfm_enrichment_progress import get_progress
from app.services.lastfm_enrichment_progress import mark_stopping
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
    }


@router.put("/settings", response_model=AppSettingsResponse, tags=["settings"])
def update_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)

    settings.cleanup_enabled = payload.cleanup_enabled
    settings.cleanup_time = payload.cleanup_time
    settings.scan_enabled = payload.scan_enabled
    settings.scan_time = payload.scan_time
    settings.lastfm_api_key = payload.lastfm_api_key

    db.commit()
    db.refresh(settings)
    refresh_scheduler_jobs()

    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
        "lastfm_api_key": settings.lastfm_api_key,
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