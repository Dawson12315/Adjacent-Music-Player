"""Whose day is it.

Play timestamps are stored as naive UTC. Days, streaks and "when you listen"
are human ideas, and the only zone the server used to know was its own —
which in a container is UTC, so everyone's evening listening landed on the
next morning. Each account can now name its zone (`users.timezone`, set from
Settings); a client that has not can pass the device's zone on the request;
and failing both the server's own zone stands, as before.

The bucketing is done here, in Python, rather than in SQL: SQLite cannot
convert to a named zone at all, and the two engines' spellings of the
conversion had drifted once already.
"""

from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, available_timezones

_known_zones: set[str] | None = None


def known_zones() -> set[str]:
    global _known_zones
    if _known_zones is None:
        _known_zones = set(available_timezones())
    return _known_zones


def normalize_zone_name(name: str | None) -> str | None:
    """The IANA name as stored, or None for anything that is not one."""
    if not name or not isinstance(name, str):
        return None
    candidate = name.strip()
    return candidate if candidate in known_zones() else None


def server_zone() -> tzinfo:
    """The zone the server process runs in — the old behaviour, kept as the fallback."""
    try:
        from tzlocal import get_localzone

        return get_localzone()
    except Exception:  # pragma: no cover - a host with no zone data at all
        return datetime.now().astimezone().tzinfo or UTC


def zone_for(user_timezone: str | None, override: str | None = None) -> tzinfo:
    """The zone an account's stats are bucketed in.

    A saved preference wins; a client's hint (its device zone) stands in
    for an account that has not chosen; the server's own zone is last.
    Both names must already have passed `normalize_zone_name`.
    """
    for name in (user_timezone, override):
        if name:
            try:
                return ZoneInfo(name)
            except Exception:
                continue
    return server_zone()


def as_local(stamp: datetime, zone: tzinfo) -> datetime:
    """A stored naive-UTC timestamp in `zone`."""
    aware = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return aware.astimezone(zone)


def local_day_of(stamp: datetime, zone: tzinfo) -> date:
    return as_local(stamp, zone).date()


def local_hour_of(stamp: datetime, zone: tzinfo) -> int:
    return as_local(stamp, zone).hour


def today_in(zone: tzinfo) -> date:
    return datetime.now(zone).date()


def utc_start_of_day(day: date, zone: tzinfo) -> datetime:
    """The naive-UTC instant at which `day` begins in `zone`, for a range filter."""
    local_midnight = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    return local_midnight.astimezone(UTC).replace(tzinfo=None)


__all__ = [
    "as_local",
    "known_zones",
    "local_day_of",
    "local_hour_of",
    "normalize_zone_name",
    "server_zone",
    "timedelta",
    "today_in",
    "utc_start_of_day",
    "zone_for",
]
