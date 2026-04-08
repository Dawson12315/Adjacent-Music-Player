from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

from app.config import settings
from app.db import Base, engine
from app import models
from app.routes.health import router as health_router
from app.routes.tracks import router as tracks_router
from app.routes.scan import router as scan_router
from app.routes.artists import router as artists_router
from app.routes.albums import router as albums_router
from app.routes.playlists import router as playlists_router
from app.db import Base, engine, SessionLocal
from app.services.playlists import ensure_liked_songs_playlist
from app.services.playback import get_or_create_playback_session
from app.routes.playback import router as playback_router
from app.routes.settings import router as settings_router
from app.routes.maintenance import router as maintenance_router
from app.services.scheduler import start_scheduler
from app.routes.artist_edit import router as artist_edit_router

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

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
app.include_router(albums_router, prefix="/api")
app.include_router(playlists_router, prefix="/api")
app.include_router(playback_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(maintenance_router, prefix="/api")
app.include_router(artist_edit_router, prefix="/api")