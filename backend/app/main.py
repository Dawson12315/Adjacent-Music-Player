import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.db_migrations import run_simple_migrations
from app.routes.albums import router as albums_router
from app.routes.artist_edit import router as artist_edit_router
from app.routes.artists import router as artists_router
from app.routes.artist_genres import router as artist_genres_router
from app.routes.genres import router as genres_router
from app.routes.health import router as health_router
from app.routes.listening import router as listening_router
from app.routes.maintenance import router as maintenance_router
from app.routes.playback import router as playback_router
from app.routes.playlists import router as playlists_router
from app.routes.scan import router as scan_router
from app.routes.settings import router as settings_router
from app.routes.stats import router as stats_router
from app.routes.tracks import router as tracks_router
from app.routes.similar_tracks import router as similar_tracks_router
from app.services.playback import get_or_create_playback_session
from app.services.playlists import ensure_liked_songs_playlist
from app.services.scheduler import start_scheduler

from app.routes import recommendation_evaluation


UPLOADS_DIR = "uploads"


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


os.makedirs(f"{UPLOADS_DIR}/artists", exist_ok=True)
os.makedirs(f"{UPLOADS_DIR}/albums", exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    os.makedirs(f"{UPLOADS_DIR}/artists", exist_ok=True)
    os.makedirs(f"{UPLOADS_DIR}/albums", exist_ok=True)
    os.makedirs(f"{UPLOADS_DIR}/playlists", exist_ok=True)

    Base.metadata.create_all(bind=engine)
    run_simple_migrations()

    db = SessionLocal()
    try:
        ensure_liked_songs_playlist(db)
        get_or_create_playback_session(db)
    finally:
        db.close()

    start_scheduler()


app.include_router(health_router, prefix="/api")
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

app.include_router(recommendation_evaluation.router, prefix="/api")