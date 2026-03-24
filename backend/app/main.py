from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, engine
from app.routes.health import router as health_router
from app.routes.tracks import router as tracks_router
from app.routes.scan import router as scan_router
from app import models

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(health_router, prefix="/api")
app.include_router(tracks_router, prefix="/api")
app.include_router(scan_router, prefix="/api")