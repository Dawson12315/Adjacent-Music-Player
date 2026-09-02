from sqlalchemy import create_engine, event, text
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
elif settings.database_url.startswith("postgresql"):
    # Sized for a handful of concurrent users plus the background jobs; none
    # of the SQLite pragma handling below applies here.
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

if settings.database_url.startswith("sqlite"):
    # foreign_keys is a per-connection setting in SQLite; running it once at
    # startup only configured whichever pooled connection happened to execute
    # it, leaving ON DELETE CASCADE dead on every other connection. Hook the
    # pool instead so every connection gets it.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    # journal_mode persists in the database file, so once is enough.
    with engine.begin() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL;"))

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