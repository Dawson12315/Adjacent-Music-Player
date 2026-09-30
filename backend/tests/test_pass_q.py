"""Pass Q: telemetry fields, edit validation, album identity.

TEL-1/2: the phone's position field is accepted under both names and the
client's clock is honoured within bounds. SET-2/3: empty titles and names are
refused. LIB-8: albums are grouped by title and artist.
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.test_pass_p import _admin, _make_track


@pytest.fixture(scope="module")
def two_greatest_hits(client, db_session_factory):
    _admin(client)
    fen = [
        _make_track(db_session_factory, f"/lib/fen-{i}.mp3", title=f"Fen {i}", artist="Fen", album="Greatest Hits")
        for i in range(2)
    ]
    olafur = [
        _make_track(db_session_factory, "/lib/olafur-0.mp3", title="Olafur 0", artist="Olafur", album="Greatest Hits")
    ]
    return fen, olafur


def _stats(db_session_factory, track_id):
    from app.models.track_user_stats import TrackUserStats

    db = db_session_factory()
    try:
        return db.query(TrackUserStats).filter_by(track_id=track_id).first()
    finally:
        db.close()


def _events(db_session_factory, track_id):
    from app.models.listening_event import ListeningEvent

    db = db_session_factory()
    try:
        return db.query(ListeningEvent).filter_by(track_id=track_id).order_by(ListeningEvent.id).all()
    finally:
        db.close()


# --- TEL-1: the position field ------------------------------------------------


def test_the_position_is_stored_under_either_name(client, db_session_factory, two_greatest_hits):
    (track_id, _), _ = two_greatest_hits

    new_name = client.post(f"/api/tracks/{track_id}/play-start", json={"source_type": "library", "position_seconds": 12.5})
    assert new_name.status_code == 200, new_name.text
    old_name = client.post(f"/api/tracks/{track_id}/skip", json={"source_type": "library", "playback_position_seconds": 40})
    assert old_name.status_code == 200, old_name.text

    positions = [event.position_seconds for event in _events(db_session_factory, track_id)]
    assert positions == [12.5, 40.0]


def test_nonsense_positions_are_tamed(client, db_session_factory, two_greatest_hits):
    (_, track_id), _ = two_greatest_hits

    assert client.post(f"/api/tracks/{track_id}/skip", json={"source_type": "library", "position_seconds": -5}).status_code == 200
    assert client.post(f"/api/tracks/{track_id}/skip", json={"source_type": "library", "position_seconds": 10**9}).status_code == 200

    positions = [event.position_seconds for event in _events(db_session_factory, track_id)]
    assert positions == [0.0, 86400.0]


# --- TEL-2: when it happened ---------------------------------------------------


def test_a_replayed_event_lands_when_it_happened(client, db_session_factory, two_greatest_hits):
    _, (track_id,) = two_greatest_hits
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    response = client.post(
        f"/api/tracks/{track_id}/play-start",
        json={"source_type": "library", "occurred_at": yesterday.isoformat()},
    )
    assert response.status_code == 200, response.text

    (event,) = _events(db_session_factory, track_id)
    assert abs((event.created_at - yesterday.replace(tzinfo=None)).total_seconds()) < 1

    stats = _stats(db_session_factory, track_id)
    assert abs((stats.last_played_at - yesterday.replace(tzinfo=None)).total_seconds()) < 1


def test_a_clock_from_the_future_or_the_distant_past_is_ignored(client, db_session_factory, two_greatest_hits):
    _, (track_id,) = two_greatest_hits
    before = datetime.now(timezone.utc).replace(tzinfo=None)

    for bad in (datetime.now(timezone.utc) + timedelta(hours=2), datetime.now(timezone.utc) - timedelta(days=30)):
        response = client.post(
            f"/api/tracks/{track_id}/play-complete",
            json={"source_type": "library", "occurred_at": bad.isoformat()},
        )
        assert response.status_code == 200, response.text

    completes = [e for e in _events(db_session_factory, track_id) if e.event_type == "play_completed"]
    assert len(completes) == 2
    for event in completes:
        assert event.created_at >= before - timedelta(seconds=1)
        assert event.created_at <= datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)

    # And "last played" is now, not yesterday's play-start from the test above.
    stats = _stats(db_session_factory, track_id)
    assert stats.last_played_at >= before - timedelta(seconds=1)


# --- SET-2 / SET-3: edits that would erase a name ---------------------------


def test_a_track_cannot_lose_its_title(client, two_greatest_hits):
    (track_id, _), _ = two_greatest_hits

    for empty in ("", "   "):
        response = client.patch(f"/api/tracks/{track_id}", json={"title": empty, "artist": "Fen"})
        assert response.status_code == 422, response.text

    too_long = client.patch(f"/api/tracks/{track_id}", json={"title": "x" * 301, "artist": "Fen"})
    assert too_long.status_code == 422

    cleaned = client.patch(f"/api/tracks/{track_id}", json={"title": "  Fen  0 ", "artist": "Fen", "album": "Greatest Hits"})
    assert cleaned.status_code == 200, cleaned.text
    assert cleaned.json()["title"] == "Fen 0"


def test_an_artist_cannot_be_renamed_to_nothing(client, two_greatest_hits):
    for empty in ("", "   "):
        response = client.patch("/api/artists/rename", json={"current_artist": "Fen", "new_artist": empty})
        assert response.status_code == 422, response.text

    response = client.patch("/api/artists/rename", json={"current_artist": "", "new_artist": "Fen"})
    assert response.status_code == 422


# --- LIB-8: album identity ----------------------------------------------------


def _items(response):
    """The rows: a bare list without a limit, a page with one."""
    body = response.json()
    return body if isinstance(body, list) else body["items"]


def test_albums_with_the_same_title_are_listed_per_artist(client, two_greatest_hits):
    response = client.get("/api/mobile/albums")
    assert response.status_code == 200, response.text

    hits = [item for item in _items(response) if item["name"] == "Greatest Hits"]
    assert sorted((item["artist"], item["trackCount"]) for item in hits) == [("Fen", 2), ("Olafur", 1)]
    assert len({item["id"] for item in hits}) == 2


def test_album_tracks_can_be_narrowed_to_one_artist(client, two_greatest_hits):
    everything = _items(client.get("/api/mobile/albums/Greatest%20Hits/tracks"))
    assert len(everything) == 3

    just_fen = _items(client.get("/api/mobile/albums/Greatest%20Hits/tracks", params={"artist": "fen"}))
    assert sorted(track["title"] for track in just_fen) == ["Fen 0", "Fen 1"]

    nobody = _items(client.get("/api/mobile/albums/Greatest%20Hits/tracks", params={"artist": "Nobody"}))
    assert nobody == []


def test_the_web_album_index_and_page_tell_artists_apart(client, two_greatest_hits):
    ids, _ = two_greatest_hits

    titles = client.get("/api/albums").json()
    assert titles.count("Greatest Hits") == 1

    detailed = [row for row in client.get("/api/albums", params={"detailed": 1}).json() if row["name"] == "Greatest Hits"]
    assert sorted((row["artist"], row["track_count"]) for row in detailed) == [("Fen", 2), ("Olafur", 1)]
    assert len({row["id"] for row in detailed}) == 2

    everything = _items(client.get("/api/albums/Greatest%20Hits/tracks"))
    assert len(everything) == 3
    fen_only = _items(client.get("/api/albums/Greatest%20Hits/tracks", params={"artist": "Fen", "fields": "list"}))
    assert sorted(track["title"] for track in fen_only) == ["Fen 0", "Fen 1"]
    assert "file_path" not in fen_only[0]
