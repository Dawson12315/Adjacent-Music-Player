from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import expression

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    recovery_codes_hashes = Column(Text, nullable=True)

    # Set when an admin hands out a generated temp password (new account or
    # reset); login then routes through the set-a-real-password screen.
    # expression.false() renders per-dialect (0 on SQLite, false on Postgres).
    must_change_password = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=expression.false(),
    )