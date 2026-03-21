from fastapi import FastAPI

from app.config import settings
from app.db import Base, engine
from app.routes.health import router as health_router

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(health_router, prefix="/api")