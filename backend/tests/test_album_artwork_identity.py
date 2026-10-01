"""Artwork belongs to one artist's record of a title, not to the title.

Setting a picture for one "Greatest Hits" changed every artist's "Greatest
Hits": the row was keyed by the title alone. A record with an artist now
has its own key; the bare title key answers only for pictures set before
records were told apart, until a record claims it.
"""

import pytest

from app.services.track_responses import (
    ARTWORK_KEY_SEPARATOR as SEP,
    album_artwork_key,
    album_artwork_keys,
    resolve_album_artwork,
)
from tests.test_pass_p import _admin, _make_track

PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 13 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_the_key_names_the_record_and_falls_back_to_the_title():
    assert album_artwork_key("Greatest  Hits", "The Band") == f"greatest hits{SEP}the band"
    assert album_artwork_key("Greatest Hits", None) == "greatest hits"
    assert album_artwork_key("", "The Band") == ""

    assert album_artwork_keys("Greatest Hits", "The Band") == [
        f"greatest hits{SEP}the band",
        "greatest hits",
    ]
    assert album_artwork_keys("Greatest Hits", "") == ["greatest hits"]
    assert album_artwork_keys(None, "The Band") == []

    art = {"greatest hits": "/u/shared.jpg", f"greatest hits{SEP}the band": "/u/band.jpg"}
    assert resolve_album_artwork(art, "Greatest Hits", "The Band") == "/u/band.jpg"
    assert resolve_album_artwork(art, "Greatest Hits", "Someone Else") == "/u/shared.jpg"
    assert resolve_album_artwork(art, "Other", "The Band") is None


@pytest.fixture(scope="module")
def two_records(client, db_session_factory):
    from app.models.album_artwork import AlbumArtwork
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack
    from app.models.track import Track
    from app.models.track_artist import TrackArtist

    _admin(client)
    one = _make_track(db_session_factory, "/lib/same-1.flac", title="One", artist="Art One", album="Same Title")
    two = _make_track(db_session_factory, "/lib/same-2.flac", title="Two", artist="Art Two", album="Same Title")
    db = db_session_factory()
    try:
        db.add(TrackArtist(track_id=one, artist_name="Art One", position=0))
        db.add(TrackArtist(track_id=two, artist_name="Art Two", position=0))
        db.commit()
    finally:
        db.close()

    yield one, two

    # The session database is shared, and these two files are not on disk:
    # left behind, they count as missing against the cleanup tests.
    db = db_session_factory()
    try:
        db.query(PlaylistTrack).filter(PlaylistTrack.track_id.in_([one, two])).delete(synchronize_session=False)
        db.query(Playlist).filter(Playlist.name == "Same Title Twice").delete(synchronize_session=False)
        db.query(TrackArtist).filter(TrackArtist.track_id.in_([one, two])).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_([one, two])).delete(synchronize_session=False)
        db.query(AlbumArtwork).filter(AlbumArtwork.album_name == "Same Title").delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _uploads_in_tmp(monkeypatch, tmp_path):
    from app.routes import albums

    monkeypatch.setattr(albums, "ALBUM_ARTWORK_DIR", str(tmp_path / "albums"))


def _upload(client, artist):
    params = {"artist": artist} if artist else {}
    return client.post(
        "/api/albums/Same Title/artwork",
        params=params,
        files={"file": ("cover.png", PNG, "image/png")},
    )


def _track_art(client, track_id):
    return client.get(f"/api/tracks/{track_id}").json()["artwork_path"]


def _record_art(client):
    rows = client.get("/api/mobile/albums").json()
    return {row["artist"]: row["artwork_path"] for row in rows if row["name"] == "Same Title"}


def test_a_picture_set_for_one_record_stays_on_that_record(client, two_records):
    one, two = two_records

    first = _upload(client, "Art One")
    assert first.status_code == 200, first.text
    assert first.json()["album_key"] == f"same title{SEP}art one"
    path_one = first.json()["artwork_path"]

    assert _track_art(client, one) == path_one
    assert _track_art(client, two) is None
    assert _record_art(client) == {"Art One": path_one, "Art Two": None}

    by_artist = client.get("/api/albums/Same Title/artwork", params={"artist": "Art Two"}).json()
    assert by_artist["artwork_path"] is None
    assert client.get("/api/albums/Same Title/artwork", params={"artist": "Art One"}).json()["artwork_path"] == path_one

    second = _upload(client, "Art Two")
    path_two = second.json()["artwork_path"]
    assert path_two != path_one
    assert _record_art(client) == {"Art One": path_one, "Art Two": path_two}

    # The bulk map carries each record under its own key.
    artwork = client.get("/api/albums/artwork").json()["artwork"]
    assert artwork[f"same title{SEP}art one"] == path_one
    assert artwork[f"same title{SEP}art two"] == path_two
    assert "same title" not in artwork

    # Lists built per track agree with the single-track answer.
    rows = client.get("/api/mobile/albums/Same Title/tracks", params={"fields": "list", "artist": "Art Two"}).json()
    rows = rows if isinstance(rows, list) else rows["items"]
    assert [row["artwork_path"] for row in rows] == [path_two]


def test_a_title_wide_picture_is_claimed_by_the_record_that_sets_one(client, db_session_factory, two_records):
    from app.models.album_artwork import AlbumArtwork

    one, two = two_records
    db = db_session_factory()
    try:
        db.query(AlbumArtwork).filter(AlbumArtwork.album_name == "Same Title").delete()
        db.add(AlbumArtwork(album_name="Same Title", album_key="same title", artwork_path="/uploads/albums/old.jpg"))
        db.commit()
    finally:
        db.close()

    # Before anyone sets a record's own picture, the old shared one shows on both.
    assert _track_art(client, one) == "/uploads/albums/old.jpg"
    assert _track_art(client, two) == "/uploads/albums/old.jpg"

    claimed = _upload(client, "Art Two").json()
    assert _track_art(client, two) == claimed["artwork_path"]
    assert _track_art(client, one) is None
    assert _record_art(client) == {"Art One": None, "Art Two": claimed["artwork_path"]}

    db = db_session_factory()
    try:
        keys = [row.album_key for row in db.query(AlbumArtwork).filter(AlbumArtwork.album_name == "Same Title")]
        assert keys == [f"same title{SEP}art two"]
    finally:
        db.close()


def test_playlist_previews_show_each_record_its_own_picture(client, two_records):
    one, two = two_records
    playlist = client.post("/api/playlists", json={"name": "Same Title Twice"}).json()
    for track_id in (one, two):
        client.post(f"/api/playlists/{playlist['id']}/tracks", json={"track_id": track_id})

    _upload(client, "Art One")
    _upload(client, "Art Two")
    rows = client.get("/api/playlists").json()
    rows = rows if isinstance(rows, list) else rows["items"]
    ours = next(row for row in rows if row["id"] == playlist["id"])
    tiles = [tile["artwork_path"] for tile in ours["preview"]]
    assert len(tiles) == 2 and tiles[0] != tiles[1] and all(tiles)
