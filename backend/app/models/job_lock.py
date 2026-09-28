from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db import Base


class JobLock(Base):
    __tablename__ = "job_locks"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False, unique=True)
    is_running = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, nullable=True)
    # Touched by long jobs as they make progress; "stale" is measured from
    # here, not from started_at, so a scan that runs for hours is never
    # mistaken for a crashed one.
    heartbeat_at = Column(DateTime, nullable=True)