import threading
import time
from datetime import datetime

from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.services.maintenance import cleanup_missing_tracks, scan_library_job

_scheduler_started = False
_last_cleanup_run = None
_last_scan_run = None


def _current_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def _current_minute_key() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _run_scheduler_loop():
    global _last_cleanup_run, _last_scan_run

    while True:
        db = SessionLocal()

        try:
            settings = db.query(AppSetting).first()

            if settings:
                now_hhmm = _current_hhmm()
                minute_key = _current_minute_key()

                if (
                    settings.cleanup_enabled
                    and settings.cleanup_time
                    and settings.cleanup_time == now_hhmm
                    and _last_cleanup_run != minute_key
                ):
                    print("Running scheduled cleanup...")
                    cleanup_missing_tracks(db)
                    _last_cleanup_run = minute_key

                if (
                    settings.scan_enabled
                    and settings.scan_time
                    and settings.scan_time == now_hhmm
                    and _last_scan_run != minute_key
                ):
                    print("Running scheduled scan...")
                    scan_library_job(db)
                    _last_scan_run = minute_key

        except Exception as error:
            print(f"Scheduler error: {error}")
        finally:
            db.close()

        time.sleep(30)


def start_scheduler():
    global _scheduler_started

    if _scheduler_started:
        return

    thread = threading.Thread(target=_run_scheduler_loop, daemon=True)
    thread.start()
    _scheduler_started = True