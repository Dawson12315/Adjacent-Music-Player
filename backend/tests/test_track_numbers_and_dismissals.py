"""Track numbers from tags and names, album order, and recycled suggestions."""

import os
from datetime import datetime, timedelta

import pytest

from app.services.filename_metadata import (
    extract_metadata_from_filename,
    extract_track_number_from_filename,
)
from app.services.metadata import parse_position
from app.services.recommendations.dismissals import (
    DISMISSAL_DAYS,
    dismiss_tracks,
    dismissed_track_ids,
    prune_expired_dismissals,
)
from tests.test_pass_p import _admin, _make_track


# --- Numbers -------------------------------------------------------------------


def test_positions_are_read_from_every_common_tag_form():
    assert parse_position("7") == 7
    assert parse_position("07") == 7
    assert parse_position("7/12") == 7
    assert parse_position(["3/10"]) == 3
    assert parse_position("") is None
    assert parse_position(None) is None
    assert parse_position("0") is None


def test_the_four_part_filename_carries_its_number():
    name = "/m/Kodak Black/Kodak The Blessing (2026)/Kodak Black - Kodak The Blessing - 15 - Idols Turn Into Rivals.flac"
    assert extract_metadata_from_filename(name) == ("Kodak Black", "Kodak The Blessing", "Idols Turn Into Rivals")
    assert extract_track_number_from_filename(name) == 15

    assert extract_track_number_from_filename("/m/a/03 Blue Harbour.mp3") == 3
    assert extract_track_number_from_filename("/m/a/03. Blue Harbour.mp3") == 3
    # A year is not a position, and a plain "Artist - Title" has none.
    assert extract_track_number_from_filename("/m/a/Band - 2019 - Song.mp3") is None
    assert extract_track_number_from_filename("/m/a/Band - Song.mp3") is None


def _credit(db_session_factory, track_ids, artist, genre=None):
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre

    db = db_session_factory()
    try:
        for track_id in track_ids:
            db.add(TrackArtist(track_id=track_id, artist_name=artist, position=0))
            if genre:
                db.add(TrackGenre(track_id=track_id, genre=genre))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def numbered_album(client, db_session_factory):
    _admin(client)
    ids = {
        "b_unnumbered": _make_track(db_session_factory, "/lib/n-x.flac", title="Zeta", artist="Numbers", album="Numbered"),
        "d2t1": _make_track(db_session_factory, "/lib/n-d2t1.flac", title="Alpha", artist="Numbers", album="Numbered", track_number=1, disc_number=2),
        "t2": _make_track(db_session_factory, "/lib/n-t2.flac", title="Yankee", artist="Numbers", album="Numbered", track_number=2),
        "t1": _make_track(db_session_factory, "/lib/n-t1.flac", title="Whiskey", artist="Numbers", album="Numbered", track_number=1),
        "t10": _make_track(db_session_factory, "/lib/n-t10.flac", title="Bravo", artist="Numbers", album="Numbered", track_number=10),
    }
    _credit(db_session_factory, ids.values(), "Numbers")
    return ids


def _items(response):
    body = response.json()
    return body if isinstance(body, list) else body["items"]


def test_album_tracks_come_back_in_record_order(client, numbered_album):
    rows = _items(client.get("/api/mobile/albums/Numbered/tracks", params={"fields": "list"}))
    assert [row["title"] for row in rows] == ["Whiskey", "Yankee", "Bravo", "Zeta", "Alpha"]
    assert [row["track_number"] for row in rows] == [1, 2, 10, None, 1]

    # The artist page keeps the same order inside each album.
    rows = _items(client.get("/api/mobile/artists/Numbers/tracks"))
    assert [row["title"] for row in rows] == ["Whiskey", "Yankee", "Bravo", "Zeta", "Alpha"]
    assert rows[0]["track_number"] == 1 and rows[-1]["disc_number"] == 2


def test_the_scanner_numbers_new_files_and_backfills_old_rows(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.services import scanner

    library = tmp_path / "lib"
    library.mkdir()

    def fake_metadata(path):
        base = {"file_path": path, "title": "Tagged Title", "artist": "Scan", "album": "Scanned", "duration_seconds": 1.0}
        if path.endswith("tagged.mp3"):
            base["track_number"] = 7
            base["disc_number"] = 1
        return base

    monkeypatch.setattr(scanner, "extract_track_metadata", fake_metadata)
    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)

    tagged = library / "tagged.mp3"
    named = library / "Scan - Scanned - 04 - Named.mp3"
    plain = library / "plain.mp3"
    for path in (tagged, named, plain):
        path.write_bytes(b"audio")
        os.utime(path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    assert scanner.scan_directory(str(library), limit=100)["added"] == 3

    db = db_session_factory()
    try:
        by_path = {t.file_path: t for t in db.query(Track).filter(Track.album == "Scanned").all()}
        assert by_path[str(tagged)].track_number == 7 and by_path[str(tagged)].disc_number == 1
        assert by_path[str(named)].track_number == 4
        # Read, and carrying no number: never read for one again.
        assert by_path[str(plain)].track_number == 0

        # A row from before numbers were read.
        by_path[str(named)].track_number = None
        by_path[str(plain)].track_number = None
        db.commit()
    finally:
        db.close()

    assert scanner.scan_directory(str(library), limit=100)["added"] == 0

    db = db_session_factory()
    try:
        by_path = {t.file_path: t for t in db.query(Track).filter(Track.album == "Scanned").all()}
        assert by_path[str(named)].track_number == 4
        assert by_path[str(plain)].track_number == 0
    finally:
        db.close()


# --- Recycled suggestions -----------------------------------------------------


@pytest.fixture(scope="module")
def two_playlists(client, db_session_factory):
    _admin(client)
    ids = [
        _make_track(db_session_factory, f"/lib/rec-{i}.flac", title=f"Rec {i:02d}", artist="Recs", album=f"Rec Album {i % 2}")
        for i in range(8)
    ]
    # One genre across the lot, so the genre retriever has candidates; the
    # genre map is cached for the session, so it is rebuilt after seeding.
    _credit(db_session_factory, ids, "Recs", genre="RecycleGenre")
    from app.services.recommendations.rec_cache import invalidate_library_caches

    invalidate_library_caches()
    first = client.post("/api/playlists", json={"name": "Recycle A"}).json()["id"]
    second = client.post("/api/playlists", json={"name": "Recycle B"}).json()["id"]
    for playlist_id in (first, second):
        for track_id in ids[:2]:
            client.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id})
    return ids, first, second


def _recommended_ids(client, playlist_id):
    body = client.get(f"/api/playlists/{playlist_id}/recommendations", params={"limit": 20}).json()
    items = body if isinstance(body, list) else body.get("recommendations", [])
    out = []
    for item in items:
        track = item.get("track") if isinstance(item, dict) and "track" in item else item
        out.append(track["id"])
    return out


def test_playlist_members_are_never_suggested_back(client, two_playlists):
    ids, first, _ = two_playlists
    suggested = _recommended_ids(client, first)
    assert not set(suggested) & set(ids[:2])


def test_recycling_holds_the_shown_rows_out_of_that_playlist_only(client, db_session_factory, two_playlists):
    ids, first, second = two_playlists
    shown = _recommended_ids(client, first)
    assert shown, "the fixture library must produce suggestions"

    recycled = client.post(
        f"/api/playlists/{first}/recommendations/recycle",
        json={"shown_track_ids": shown, "refresh": 1, "limit": 20},
    )
    assert recycled.status_code == 200, recycled.text

    assert not set(_recommended_ids(client, first)) & set(shown)
    # The other playlist still gets them.
    assert set(_recommended_ids(client, second)) & set(shown)

    db = db_session_factory()
    try:
        from app.models.user import User

        user_id = db.query(User).filter_by(username="admin").one().id
        assert set(dismissed_track_ids(db, user_id, first)) == set(shown)
        assert dismissed_track_ids(db, user_id, second) == []

        # After the hold, they are back; a second recycle restamps.
        later = datetime.utcnow() + timedelta(days=DISMISSAL_DAYS, seconds=1)
        assert dismissed_track_ids(db, user_id, first, now=later) == []
        dismiss_tracks(db, user_id, first, shown[:1], now=later)
        assert dismissed_track_ids(db, user_id, first, now=later) == shown[:1]

        assert prune_expired_dismissals(db, now=later) == len(shown) - 1
        assert prune_expired_dismissals(db, now=later + timedelta(days=DISMISSAL_DAYS, seconds=1)) == 1
    finally:
        db.close()


def test_recycling_someone_elses_playlist_is_refused(client, two_playlists):
    _, first, _ = two_playlists
    response = client.post("/api/playlists/999999/recommendations/recycle", json={"shown_track_ids": [1]})
    assert response.status_code == 404
