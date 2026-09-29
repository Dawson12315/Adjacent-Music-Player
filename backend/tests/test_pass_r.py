"""Pass R: less on the wire, less per page.

PERF-4: `fields=list` returns the row a list draws from. PERF-5/DATA-14:
the artist and album indexes page in SQL and stay consistent across pages.
PERF-6: loved ids without the rows. PERF-7: top genres on their own.
PERF-17: weak ETags on the index routes.
"""

import pytest

from app.middleware.etag import etag_matches
from app.services.track_responses import LIST_FIELDS
from tests.test_pass_p import _admin, _make_track


@pytest.fixture(scope="module")
def indexed_library(client, db_session_factory):
    from app.models.album_artwork import AlbumArtwork
    from app.models.playlist_track import PlaylistTrack
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre

    _admin(client)
    ids = []
    db = db_session_factory()
    try:
        # Names no other module uses: the session database is shared.
        for i in range(12):
            artist = f"Pass R Artist {i % 4:02d}"
            album = f"Pass R Album {i % 3:02d}"
            track_id = _make_track(
                db_session_factory,
                f"/lib/r-{i}.flac",
                title=f"Pass R Song {i:02d}",
                artist=artist,
                album=album,
                duration_seconds=100 + i,
            )
            ids.append(track_id)
            db.add(TrackArtist(track_id=track_id, artist_name=artist, position=0))
            db.add(TrackGenre(track_id=track_id, genre="PassRFolk" if i % 2 else "PassRAmbient"))
        db.add(
            AlbumArtwork(
                album_name="Pass R Album 00",
                album_key="pass r album 00",
                artwork_path="/uploads/albums/pass-r.jpg",
            )
        )
        db.commit()
    finally:
        db.close()

    liked = client.get("/api/playlists/liked-songs").json()
    for track_id in ids[:3]:
        client.post("/api/playlists/liked-songs/tracks", json={"track_id": track_id})
    for track_id in ids[:5]:
        client.post(f"/api/tracks/{track_id}/play-start", json={"source_type": "library"})

    yield ids, liked["id"]

    # Later modules read Ducking Good's preview; leave it as it was.
    for track_id in ids[:3]:
        client.delete(f"/api/playlists/liked-songs/tracks/{track_id}")


def _items(response):
    body = response.json()
    return body if isinstance(body, list) else body["items"]


# --- PERF-4: the list projection ---------------------------------------------


def test_the_list_projection_is_the_row_and_nothing_else(client, indexed_library):
    ids, _ = indexed_library

    page = client.get("/api/tracks", params={"limit": 5, "fields": "list", "search": "Pass R"}).json()
    assert page["total"] == 12
    for row in page["items"]:
        assert set(row) == set(LIST_FIELDS), row
    first = next(row for row in page["items"] if row["album"] == "Pass R Album 00")
    assert first["artwork_path"] == "/uploads/albums/pass-r.jpg"
    assert first["file_ext"] == "flac"
    assert first["genres"] in (["PassRFolk"], ["PassRAmbient"])

    full = client.get("/api/tracks", params={"limit": 1}).json()["items"][0]
    assert "file_path" in full and "raw_title" in full

    assert client.get("/api/tracks", params={"limit": 1, "fields": "everything"}).status_code == 422


def test_every_list_route_takes_the_projection(client, indexed_library):
    ids, liked_id = indexed_library

    for path in (
        "/api/mobile/artists/Pass%20R%20Artist%2000/tracks",
        "/api/mobile/albums/Pass%20R%20Album%2000/tracks",
        "/api/genres/PassRFolk/tracks",
        f"/api/playlists/{liked_id}/tracks",
        "/api/stats/recently-played",
    ):
        rows = _items(client.get(path, params={"fields": "list", "limit": 50}))
        ours = [row for row in rows if str(row["title"]).startswith("Pass R Song")]
        assert ours, path
        for row in rows:
            assert "file_path" not in row, path
            assert "file_ext" in row and "duration_seconds" in row, path
        assert all(row["file_ext"] == "flac" for row in ours), path

    genre_rows = _items(client.get("/api/genres/PassRFolk/tracks", params={"fields": "list"}))
    assert all("play_count" in row for row in genre_rows)


# --- PERF-5 / DATA-14: SQL-side paging -----------------------------------------


def _walk_pages(client, path, limit):
    seen, offset, total = [], 0, None
    while True:
        page = client.get(path, params={"limit": limit, "offset": offset}).json()
        assert page["limit"] == limit and page["offset"] == offset
        total = page["total"] if total is None else total
        assert page["total"] == total
        seen.extend(page["items"])
        if not page["has_more"]:
            break
        assert len(page["items"]) == limit
        offset += len(page["items"])
    return seen, total


def test_artist_pages_agree_with_the_flat_list(client, indexed_library):
    flat = client.get("/api/mobile/artists").json()
    assert isinstance(flat, list)
    paged, total = _walk_pages(client, "/api/mobile/artists", 3)

    assert total == len(flat)
    assert [row["name"] for row in paged] == [row["name"] for row in flat]
    ours = next(row for row in paged if row["name"] == "Pass R Artist 00")
    assert ours["trackCount"] == 3 and ours["albumCount"] == 3


def test_album_pages_agree_with_the_flat_list(client, indexed_library):
    flat = client.get("/api/mobile/albums").json()
    paged, total = _walk_pages(client, "/api/mobile/albums", 5)

    assert total == len(flat)
    assert [row["id"] for row in paged] == [row["id"] for row in flat]
    with_art = [row for row in paged if row["name"] == "Pass R Album 00"]
    assert with_art and all(row["artwork_path"] == "/uploads/albums/pass-r.jpg" for row in with_art)

    empty = client.get("/api/mobile/albums", params={"limit": 5, "offset": 10_000}).json()
    assert empty["items"] == [] and empty["has_more"] is False and empty["total"] == total


# --- PERF-6 / PERF-7: ids and genres on their own -----------------------------


def test_loved_ids_come_without_the_rows(client, indexed_library):
    ids, liked_id = indexed_library

    body = client.get("/api/playlists/liked-songs/track-ids").json()
    assert body["playlist_id"] == liked_id
    assert body["track_ids"] == ids[:3]


def test_top_genres_stand_alone_and_match_the_overview(client, indexed_library):
    genres = client.get("/api/stats/top-genres", params={"limit": 10}).json()
    overview = client.get("/api/stats/overview", params={"limit": 10}).json()

    assert genres == overview["top_genres"]
    ours = {row["name"]: row["play_count"] for row in genres if row["name"].startswith("PassR")}
    assert set(ours) == {"PassRFolk", "PassRAmbient"}
    assert sum(ours.values()) == 5


# --- PERF-17: ETags ------------------------------------------------------------


def test_index_routes_answer_304_to_a_matching_etag(client, indexed_library):
    first = client.get("/api/mobile/albums", params={"limit": 50})
    assert first.status_code == 200
    etag = first.headers.get("etag")
    assert etag and etag.startswith('W/"')
    assert first.headers.get("cache-control") == "private, no-cache"

    again = client.get("/api/mobile/albums", params={"limit": 50}, headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers.get("etag") == etag

    other = client.get("/api/mobile/albums", params={"limit": 50}, headers={"If-None-Match": 'W/"nope"'})
    assert other.status_code == 200


def test_the_etag_moves_when_the_answer_does(client, indexed_library):
    before = client.get("/api/playlists")
    etag = before.headers["etag"]

    created = client.post("/api/playlists", json={"name": "Pass R"})
    assert created.status_code in (200, 201), created.text

    after = client.get("/api/playlists", headers={"If-None-Match": etag})
    assert after.status_code == 200
    assert after.headers["etag"] != etag


def test_streams_and_errors_are_left_alone(client, indexed_library):
    ids, _ = indexed_library

    missing = client.get("/api/tracks/999999")
    assert missing.status_code == 404
    assert "etag" not in missing.headers

    # A stream is not JSON and is never buffered.
    stream = client.get(f"/api/tracks/{ids[0]}/stream")
    assert "etag" not in stream.headers


def test_etag_matching_handles_lists_and_weak_markers():
    assert etag_matches('W/"abc"', 'W/"abc"')
    assert etag_matches('"abc"', 'W/"abc"')
    assert etag_matches('W/"x", W/"abc"', 'W/"abc"')
    assert etag_matches("*", 'W/"abc"')
    assert not etag_matches('W/"abd"', 'W/"abc"')
    assert not etag_matches(None, 'W/"abc"')
