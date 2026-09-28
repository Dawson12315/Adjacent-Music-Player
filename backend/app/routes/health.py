"""Is the server actually able to serve?

A bare `{"status":"ok"}` reported healthy with the music share unmounted, the
database locked and no ffmpeg on the path — and Docker, the frontend's
`depends_on` and the phone all believed it. The checks below are the three
things that make playback possible; each is cheap enough to answer a poll
every fifteen seconds.

The body also says what this server can do, so a phone can tell "old server"
from "deleted thing" instead of mapping every 404 to "not there any more".
"""

import os
import shutil

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

router = APIRouter()

# Bumped whenever a client-facing route or field is added. Clients compare it
# with the version they were built against.
API_VERSION = 3

# The oldest mobile build this API still serves whole.
MIN_CLIENT_VERSION = "1.0.31"

CAPABILITIES = [
    "paged-lists",
    "home-rails",
    "insights",
    "stream-token-header",
    "hls",
    "scan-progress",
    "offline-manifest",
    "health-status",
]

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def _library_mounted() -> bool:
    path = settings.music_library_path
    try:
        if not os.path.isdir(path):
            return False
        with os.scandir(path) as entries:
            return next(entries, None) is not None
    except OSError:
        return False


def _database_answers() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        db.close()


@router.get("/health", tags=["health"])
def health_check(response: Response):
    checks = {
        "library": _library_mounted(),
        "database": _database_answers(),
        "ffmpeg": _FFMPEG_AVAILABLE,
    }
    healthy = all(checks.values())

    if not healthy:
        response.status_code = 503

    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "api_version": API_VERSION,
        "min_client": MIN_CLIENT_VERSION,
        "capabilities": CAPABILITIES,
    }
