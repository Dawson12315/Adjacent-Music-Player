"""SQL expressions that need a per-engine spelling.

The app runs on SQLite (single-user default) and PostgreSQL (multi-user).
SQLAlchemy abstracts almost everything; the exceptions live here so route code
stays engine-neutral.
"""

from sqlalchemy import func

from app.db import engine


def hour_of_day(column):
    """Bucket a naive-UTC timestamp column into server-local hour "00".."23".

    Timestamps are stored naive in UTC on both engines (datetime.utcnow
    defaults throughout the models). SQLite's strftime with the 'localtime'
    modifier does the UTC→local conversion in one step; Postgres needs the
    two-step timezone() dance — interpret as UTC, convert to the server zone —
    before formatting. Both return zero-padded strings, so GROUP BY and the
    int() parsing at the call site behave identically.
    """
    if engine.dialect.name == "sqlite":
        return func.strftime("%H", column, "localtime")

    from tzlocal import get_localzone_name

    localized = func.timezone(get_localzone_name(), func.timezone("UTC", column))
    return func.to_char(localized, "HH24")
