"""Insights count the day where the listener lives.

Play timestamps are naive UTC. Days, streaks and hours used to be bucketed
in the server's own zone — UTC in a container — so an evening's listening
landed on the next morning for everyone west of Greenwich. Each account can
name its zone; a client can hint its device's; the server's zone is last.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.timezones import (
    local_day_of,
    local_hour_of,
    normalize_zone_name,
    utc_start_of_day,
    zone_for,
)
from tests.test_pass_p import _admin, _make_track

SYDNEY = "Australia/Sydney"
LOS_ANGELES = "America/Los_Angeles"


# --- the service ---------------------------------------------------------------


def test_only_real_zone_names_are_accepted():
    assert normalize_zone_name(" Europe/London ") == "Europe/London"
    assert normalize_zone_name("Mars/Olympus_Mons") is None
    assert normalize_zone_name("") is None
    assert normalize_zone_name(None) is None


def test_a_saved_zone_beats_the_clients_hint_beats_the_server():
    assert str(zone_for(SYDNEY, LOS_ANGELES)) == SYDNEY
    assert str(zone_for(None, LOS_ANGELES)) == LOS_ANGELES
    assert zone_for(None, None) is not None


def test_one_instant_is_two_different_days():
    stamp = datetime(2026, 10, 5, 23, 30)  # naive UTC, as stored

    assert local_day_of(stamp, ZoneInfo(SYDNEY)).isoformat() == "2026-10-06"
    assert local_day_of(stamp, ZoneInfo(LOS_ANGELES)).isoformat() == "2026-10-05"
    assert local_hour_of(stamp, ZoneInfo(SYDNEY)) == 10
    assert local_hour_of(stamp, ZoneInfo(LOS_ANGELES)) == 16


def test_the_start_of_a_local_day_in_utc():
    # Sydney's 6 October begins at 13:00 UTC on the 5th (AEDT, +11).
    assert utc_start_of_day(datetime(2026, 10, 6).date(), ZoneInfo(SYDNEY)) == datetime(2026, 10, 5, 13, 0)


# --- over HTTP -----------------------------------------------------------------


@pytest.fixture(scope="module")
def evening_play(client, db_session_factory):
    """One play at 23:30 UTC yesterday, which is today in Sydney and yesterday in LA."""
    from app.models.listening_event import ListeningEvent
    from app.models.user import User

    _admin(client)
    track_id = _make_track(db_session_factory, "/lib/tz-evening.flac", title="Late", artist="Owl")
    stamp = (datetime.now(UTC) - timedelta(days=1)).replace(hour=23, minute=30, second=0, microsecond=0, tzinfo=None)

    db = db_session_factory()
    try:
        admin = db.query(User).filter_by(username="admin").one()
        event = ListeningEvent(
            user_id=admin.id, track_id=track_id, event_type="play_started", created_at=stamp
        )
        db.add(event)
        db.commit()
        event_id = event.id
    finally:
        db.close()

    yield {"stamp": stamp, "track_id": track_id}

    db = db_session_factory()
    try:
        db.query(ListeningEvent).filter(ListeningEvent.id == event_id).delete()
        admin = db.query(User).filter_by(username="admin").one()
        admin.timezone = None
        db.commit()
    finally:
        db.close()


def _day_with_play(client, tz):
    rows = client.get("/api/stats/plays-over-time", params={"days": 3, "tz": tz}).json()
    return [row["date"] for row in rows if row["plays"] > 0]


def test_the_device_zone_decides_which_day_a_play_lands_on(client, evening_play):
    stamp = evening_play["stamp"]
    sydney_day = local_day_of(stamp, ZoneInfo(SYDNEY)).isoformat()
    la_day = local_day_of(stamp, ZoneInfo(LOS_ANGELES)).isoformat()

    assert sydney_day != la_day
    assert sydney_day in _day_with_play(client, SYDNEY)
    assert la_day in _day_with_play(client, LOS_ANGELES)
    assert sydney_day not in _day_with_play(client, LOS_ANGELES)


def test_the_hour_follows_the_zone_too(client, evening_play):
    stamp = evening_play["stamp"]

    def hours(tz):
        return {row["hour"] for row in client.get("/api/stats/by-hour", params={"tz": tz}).json() if row["plays"]}

    assert local_hour_of(stamp, ZoneInfo(SYDNEY)) in hours(SYDNEY)
    assert local_hour_of(stamp, ZoneInfo(LOS_ANGELES)) in hours(LOS_ANGELES)
    assert hours(SYDNEY) != hours(LOS_ANGELES)


def test_a_zone_that_is_not_one_is_refused(client, evening_play):
    assert client.get("/api/stats/by-hour", params={"tz": "Mars/Olympus_Mons"}).status_code == 422
    assert client.get("/api/stats/summary", params={"tz": "nope"}).status_code == 422


def test_a_saved_preference_wins_over_the_devices_hint(client, evening_play):
    stamp = evening_play["stamp"]
    sydney_day = local_day_of(stamp, ZoneInfo(SYDNEY)).isoformat()

    saved = client.patch("/api/auth/me/preferences", json={"timezone": SYDNEY})
    assert saved.status_code == 200
    assert saved.json()["timezone"] == SYDNEY
    assert client.get("/api/auth/me").json()["timezone"] == SYDNEY

    # The phone says it is in Los Angeles; the account said Sydney, and the
    # account was asked first.
    assert sydney_day in _day_with_play(client, LOS_ANGELES)

    cleared = client.patch("/api/auth/me/preferences", json={"timezone": None})
    assert cleared.status_code == 200
    assert cleared.json()["timezone"] is None
    assert sydney_day not in _day_with_play(client, LOS_ANGELES)


def test_the_preference_refuses_a_made_up_zone_and_needs_no_password(client, evening_play):
    refused = client.patch("/api/auth/me/preferences", json={"timezone": "Mars/Olympus_Mons"})
    assert refused.status_code == 422

    body = client.patch("/api/auth/me/preferences", json={"timezone": "Europe/London"}).json()
    assert body["timezone"] == "Europe/London"
    client.patch("/api/auth/me/preferences", json={"timezone": None})


def test_streaks_are_counted_in_the_zone(client, evening_play):
    # In Sydney the play is today: a one-day current streak. In LA it was
    # yesterday: still a current streak (yesterday counts), days_active one.
    for tz in (SYDNEY, LOS_ANGELES):
        summary = client.get("/api/stats/summary", params={"tz": tz}).json()
        assert summary["days_active"] >= 1
        assert summary["current_streak_days"] >= 1


def test_top_rows_carry_artwork_fields(client, evening_play):
    artists = client.get("/api/stats/top-artists", params={"limit": 3}).json()
    albums = client.get("/api/stats/top-albums", params={"limit": 3}).json()

    assert artists and "artwork_path" in artists[0]
    assert "name" in artists[0] and "play_count" in artists[0]
    # The seeded track has no album; whichever rows there are carry the field.
    for row in albums:
        assert set(row) >= {"name", "artist", "play_count", "artwork_path"}
