"""Test environment bootstrap.

The app's config, engine and session factory are module-level singletons, so
the environment must be decided before anything under `app` is imported.
conftest is imported before any test module, which makes this the one safe
place to do it.

Engine selection: tests run on whatever DATABASE_URL says — CI runs the suite
once against SQLite and once against a real PostgreSQL service container.
With no DATABASE_URL, a throwaway SQLite file is used so a bare `pytest` can
never touch a developer's real data/app.db.
"""

import os
import tempfile

if not os.environ.get("DATABASE_URL"):
    _tmp_dir = tempfile.mkdtemp(prefix="adjacent-tests-")
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"

os.environ.setdefault("AUTH_SECRET_KEY", "adjacent-test-secret-key-0123456789abcdef")
os.environ.setdefault("MUSIC_LIBRARY_PATH", tempfile.mkdtemp(prefix="adjacent-lib-"))
os.environ.setdefault("APP_ENV", "development")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def fresh_schema():
    """Start every suite run from an empty schema.

    Matters for the Postgres matrix leg, where the service container survives
    between retries of a CI job. Refuses to run against anything that looks
    like a real install's database.
    """
    from app.db import Base, engine

    url = str(engine.url)
    if url.endswith("data/app.db"):
        raise RuntimeError(
            "Refusing to run tests against data/app.db — set DATABASE_URL "
            "to a disposable database."
        )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="session")
def client(fresh_schema):
    from app.main import app

    # Context manager so FastAPI startup/shutdown hooks run (create_all,
    # migrations, scheduler) — the same code path a real boot takes.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_session_factory(fresh_schema):
    from app.db import SessionLocal

    return SessionLocal
