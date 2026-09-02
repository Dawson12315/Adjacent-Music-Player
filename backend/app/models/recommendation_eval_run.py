from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text, text

from app.db import Base


class RecommendationEvalRun(Base):
    """One row per offline recommendation-evaluation run.

    The table predates this model — evaluation.py talks to it with raw SQL and
    the SQLite migration runner creates it there. The model exists so
    Base.metadata knows the table: Postgres schemas are created solely from
    the models, and the migration copier walks metadata.sorted_tables.
    """

    __tablename__ = "recommendation_eval_runs"

    id = Column(Integer, primary_key=True)
    kind = Column(Text, nullable=False)
    params_json = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False)
    # server_default matches the legacy SQLite DDL, so tables born from
    # create_all behave the same as ones born from the migration runner.
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
