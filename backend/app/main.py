import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.types import Receive, Scope, Send

from app import models
from app.config import settings
from app.db import Base, engine
from app.db_migrations import run_simple_migrations
from app.routes.albums import router as albums_router
from app.routes.artist_edit import router as artist_edit_router
from app.routes.artists import router as artists_router
from app.routes.artist_genres import router as artist_genres_router
from app.routes.auth import router as auth_router
from app.routes.genres import router as genres_router
from app.routes.health import router as health_router
from app.routes.home import router as home_router
from app.routes.listening import router as listening_router
from app.routes.maintenance import router as maintenance_router
from app.routes.playback import router as playback_router
from app.routes.playlists import router as playlists_router
from app.routes.scan import router as scan_router
from app.routes.settings import router as settings_router
from app.routes.similar_tracks import router as similar_tracks_router
from app.routes.stats import router as stats_router
from app.routes.tracks import router as tracks_router
from app.services.job_locking import release_all_job_locks
from app.services.scheduler import start_scheduler

from app.routes import recommendation_evaluation


# Application loggers (uvicorn configures only its own); INFO keeps job and
# transcode progress visible without the per-request noise the old print()
# calls produced.
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

UPLOADS_DIR = "data/uploads"
LEGACY_UPLOADS_DIR = "app/uploads"

# GZipMiddleware has no path exclusions and will compress 206 Partial Content
# bodies, which leaves the Content-Range byte offsets describing the
# uncompressed file and breaks seeking in the audio players. Audio payloads are
# already compressed, so nothing is lost by passing them through untouched.
# Audio streaming must bypass gzip: compressing a 206 response leaves Content-Range
# describing uncompressed offsets, which breaks seeking. Uploaded artwork is already
# JPEG/PNG/WebP, so re-compressing it costs CPU and can grow the payload.
GZIP_EXCLUDED_PATH_MARKERS = (
    "/stream",
    "/mobile-stream",
    "/hls/",
    "/uploads",
    "/legacy-uploads",
)


class StreamSafeGZipMiddleware(GZipMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and any(
            marker in scope.get("path", "")
            for marker in GZIP_EXCLUDED_PATH_MARKERS
        ):
            await self.app(scope, receive, send)
            return

        await super().__call__(scope, receive, send)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


def ensure_upload_dirs():
    os.makedirs(f"{UPLOADS_DIR}/artists", exist_ok=True)
    os.makedirs(f"{UPLOADS_DIR}/albums", exist_ok=True)
    os.makedirs(f"{UPLOADS_DIR}/playlist_artwork", exist_ok=True)


ensure_upload_dirs()

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

if os.path.exists(LEGACY_UPLOADS_DIR):
    app.mount(
        "/legacy-uploads",
        StaticFiles(directory=LEGACY_UPLOADS_DIR),
        name="legacy-uploads",
    )


# The Vite dev server origin is a development convenience only; a production
# API should trust exactly the origin it was configured with.
cors_origins = [settings.frontend_origin]

if not settings.is_production and "http://localhost:5173" not in cors_origins:
    cors_origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    StreamSafeGZipMiddleware,
    minimum_size=1000,
)


@app.on_event("startup")
def on_startup():
    ensure_upload_dirs()

    Base.metadata.create_all(bind=engine)
    run_simple_migrations()

    # Jobs die with the process; their locks must not survive it.
    release_all_job_locks()

    start_scheduler()

    _rebuild_cooccurrence_if_empty()


def _rebuild_cooccurrence_if_empty():
    """Self-heal: the table is derived data, so an empty table alongside
    existing listening/playlist history just means the rebuild never ran."""
    import threading

    from sqlalchemy import func as sa_func

    from app.db import SessionLocal
    from app.models.listening_event import ListeningEvent
    from app.models.playlist_track import PlaylistTrack
    from app.models.track_cooccurrence import TrackCooccurrence
    from app.services.recommendations.cooccurrence_builder import (
        rebuild_track_cooccurrence_standalone,
    )

    db = SessionLocal()
    try:
        has_pairs = db.query(TrackCooccurrence.id).first() is not None
        if has_pairs:
            return

        has_source_data = (
            db.query(sa_func.count(ListeningEvent.id)).scalar() or 0
        ) > 0 or (db.query(sa_func.count(PlaylistTrack.id)).scalar() or 0) > 1

        if not has_source_data:
            return
    finally:
        db.close()

    threading.Thread(
        target=rebuild_track_cooccurrence_standalone,
        name="cooccurrence-rebuild",
        daemon=True,
    ).start()


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

app.include_router(tracks_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(artists_router, prefix="/api")
app.include_router(artist_genres_router, prefix="/api")
app.include_router(albums_router, prefix="/api")
app.include_router(playlists_router, prefix="/api")
app.include_router(playback_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(maintenance_router, prefix="/api")
app.include_router(artist_edit_router, prefix="/api")
app.include_router(genres_router, prefix="/api")
app.include_router(similar_tracks_router, prefix="/api")
app.include_router(listening_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(home_router, prefix="/api")
app.include_router(recommendation_evaluation.router, prefix="/api")