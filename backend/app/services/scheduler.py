import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.lastfm_enrichment_runner import run_lastfm_enrichment_with_lock
from app.services.maintenance import (
    CleanupRefused,
    LibraryUnavailable,
    cleanup_missing_tracks,
)

logger = logging.getLogger(__name__)

_scheduler = None


def _run_cleanup_job():
    db = SessionLocal()

    try:
        # Decided outside the try/finally that releases: a skipped run must
        # not release the lock the running cleanup holds.
        if not try_acquire_job_lock(db, "cleanup"):
            logger.warning("Cleanup skipped: already running")
            return

        try:
            logger.info("Running scheduled cleanup...")
            result = cleanup_missing_tracks(db)
            logger.info("Scheduled cleanup: %s", result)
        except LibraryUnavailable as error:
            db.rollback()
            logger.warning("Scheduled cleanup refused: %s", error)
        except CleanupRefused as error:
            logger.warning(
                "Scheduled cleanup refused: %s Run it from Settings to confirm.",
                error,
            )
        except Exception:
            db.rollback()
            logger.exception("Scheduled cleanup error")
        finally:
            try:
                release_job_lock(db, "cleanup")
            except Exception:
                pass
    finally:
        db.close()


def _run_scan_job():
    # One code path for every scan: the background runner owns the job lock,
    # the progress the clients poll, and the cache invalidation afterwards.
    # Running scan_directory inline here left the phone's scan panel saying
    # nothing was running while the nightly scan was an hour in.
    from app.services.scan_runner import start_scan_background

    result = start_scan_background(limit=100000)
    if result["started"]:
        logger.info("Scheduled scan started")
    else:
        logger.warning("Scheduled scan skipped: %s", result["reason"])


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
        logger.warning(f"Scheduler sync error: {error}")
    finally:
        db.close()


def _run_cooccurrence_rebuild_job():
    from app.services.recommendations.cooccurrence_builder import (
        rebuild_track_cooccurrence_standalone,
    )

    try:
        rebuild_track_cooccurrence_standalone()
    except Exception as error:
        logger.warning(f"Scheduled co-occurrence rebuild error: {error}")


def _run_stream_cache_sweep_job():
    from app.services.stream_cache_maintenance import sweep_stream_caches

    try:
        sweep_stream_caches()
    except Exception as error:
        logger.warning(f"Scheduled stream cache sweep error: {error}")


def _run_database_backup_job():
    from app.services.db_backup import run_nightly_backup

    run_nightly_backup()


def start_scheduler():
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.start()

    # Not settings-gated: a consistent copy of the SQLite database, written
    # with the online backup API, kept for a week. Copying app.db by hand
    # while the server runs misses whatever is still in the WAL.
    _scheduler.add_job(
        _run_database_backup_job,
        trigger="cron",
        hour=2,
        minute=45,
        id="scheduled_database_backup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Not settings-gated: co-occurrence is derived data that silently rots
    # when listening or playlists change, and the rebuild is cheap.
    _scheduler.add_job(
        _run_cooccurrence_rebuild_job,
        trigger="cron",
        hour=3,
        minute=45,
        id="scheduled_cooccurrence_rebuild",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Transcode caches only ever grow without this; the sweep also removes
    # entries orphaned by purge/cleanup and superseded naming schemes.
    _scheduler.add_job(
        _run_stream_cache_sweep_job,
        trigger="cron",
        hour=4,
        minute=15,
        id="scheduled_stream_cache_sweep",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _sync_scheduler_jobs()


def refresh_scheduler_jobs():
    _sync_scheduler_jobs()
