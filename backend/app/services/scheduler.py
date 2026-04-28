from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.lastfm_enrichment_runner import run_lastfm_enrichment_with_lock
from app.services.maintenance import cleanup_missing_tracks, scan_library_job


_scheduler = None


def _run_cleanup_job():
    db = SessionLocal()

    try:
        if not try_acquire_job_lock(db, "cleanup"):
            print("Cleanup skipped: already running")
            return

        print("Running scheduled cleanup...")
        cleanup_missing_tracks(db)
    except Exception as error:
        print(f"Scheduled cleanup error: {error}")
    finally:
        try:
            release_job_lock(db, "cleanup")
        except Exception:
            pass
        db.close()


def _run_scan_job():
    db = SessionLocal()

    try:
        if not try_acquire_job_lock(db, "scan"):
            print("Scan skipped: already running")
            return

        print("Running scheduled scan...")
        scan_library_job(db)
    except Exception as error:
        print(f"Scheduled scan error: {error}")
    finally:
        try:
            release_job_lock(db, "scan")
        except Exception:
            pass
        db.close()


def _run_lastfm_enrichment_job():
    run_lastfm_enrichment_with_lock()


def _sync_scheduler_jobs():
    global _scheduler

    if _scheduler is None:
        return

    db = SessionLocal()

    try:
        settings = db.query(AppSetting).first()

        cleanup_job_id = "scheduled_cleanup"
        scan_job_id = "scheduled_scan"
        lastfm_enrichment_job_id = "scheduled_lastfm_enrichment"

        existing_cleanup = _scheduler.get_job(cleanup_job_id)
        existing_scan = _scheduler.get_job(scan_job_id)
        existing_lastfm_enrichment = _scheduler.get_job(lastfm_enrichment_job_id)

        if settings and settings.cleanup_enabled and settings.cleanup_time:
            cleanup_hour, cleanup_minute = settings.cleanup_time.split(":")
            if existing_cleanup:
                _scheduler.remove_job(cleanup_job_id)

            _scheduler.add_job(
                _run_cleanup_job,
                trigger="cron",
                hour=int(cleanup_hour),
                minute=int(cleanup_minute),
                id=cleanup_job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        elif existing_cleanup:
            _scheduler.remove_job(cleanup_job_id)

        if settings and settings.scan_enabled and settings.scan_time:
            scan_hour, scan_minute = settings.scan_time.split(":")
            if existing_scan:
                _scheduler.remove_job(scan_job_id)

            _scheduler.add_job(
                _run_scan_job,
                trigger="cron",
                hour=int(scan_hour),
                minute=int(scan_minute),
                id=scan_job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        elif existing_scan:
            _scheduler.remove_job(scan_job_id)

        if (
            settings
            and settings.lastfm_enrichment_enabled
            and settings.lastfm_enrichment_time
        ):
            lastfm_hour, lastfm_minute = settings.lastfm_enrichment_time.split(":")
            if existing_lastfm_enrichment:
                _scheduler.remove_job(lastfm_enrichment_job_id)

            _scheduler.add_job(
                _run_lastfm_enrichment_job,
                trigger="cron",
                hour=int(lastfm_hour),
                minute=int(lastfm_minute),
                id=lastfm_enrichment_job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        elif existing_lastfm_enrichment:
            _scheduler.remove_job(lastfm_enrichment_job_id)

    except Exception as error:
        print(f"Scheduler sync error: {error}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.start()
    _sync_scheduler_jobs()


def refresh_scheduler_jobs():
    _sync_scheduler_jobs()