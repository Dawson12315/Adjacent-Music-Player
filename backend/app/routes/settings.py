from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.app_setting import AppSetting
from app.schemas.settings import AppSettingsResponse, AppSettingsUpdate
from app.services.scheduler import refresh_scheduler_jobs

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
    }


@router.put("/settings", response_model=AppSettingsResponse, tags=["settings"])
def update_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)

    settings.cleanup_enabled = payload.cleanup_enabled
    settings.cleanup_time = payload.cleanup_time
    settings.scan_enabled = payload.scan_enabled
    settings.scan_time = payload.scan_time

    db.commit()
    db.refresh(settings)
    refresh_scheduler_jobs()

    return {
        "cleanup_enabled": settings.cleanup_enabled,
        "cleanup_time": settings.cleanup_time,
        "scan_enabled": settings.scan_enabled,
        "scan_time": settings.scan_time,
    }