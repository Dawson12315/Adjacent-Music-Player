from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {}
engine_kwargs = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }
    engine_kwargs = {
        "pool_pre_ping": True,
    }

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

if settings.database_url.startswith("sqlite"):
    with engine.begin() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL;"))
        connection.execute(text("PRAGMA synchronous=NORMAL;"))
        connection.execute(text("PRAGMA foreign_keys=ON;"))

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()