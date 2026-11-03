"""Playlists read newest first: a track added now goes to the top, Ducking
Good included, and existing playlists were turned over once."""
from sqlalchemy import text

from tests.test_pass_p import _admin, _make_track


def _ids(client, playlist_id):
    rows = client.get(f"/api/playlists/{playlist_id}/tracks").json()
    items = rows.get("items", rows) if isinstance(rows, dict) else rows
    return [item["id"] for item in items]


def test_a_track_added_to_a_playlist_goes_to_the_top(client, db_session_factory):
    _admin(client)
    a, b, c = (_make_track(db_session_factory, f"/nf/{name}.flac", title=name, artist="Newest First") for name in ("a", "b", "c"))
    playlist = client.post("/api/playlists", json={"name": "Newest First"}).json()
    for track_id in (a, b, c):
        assert client.post(f"/api/playlists/{playlist['id']}/tracks", json={"track_id": track_id}).status_code == 200
    assert _ids(client, playlist["id"]) == [c, b, a]

    # Taking one out keeps the rest in order and the positions compact.
    assert client.delete(f"/api/playlists/{playlist['id']}/tracks/{b}").status_code == 200
    assert _ids(client, playlist["id"]) == [c, a]
    db = db_session_factory()
    try:
        positions = [r[0] for r in db.execute(text("select position from playlist_tracks where playlist_id = :p order by position"), {"p": playlist["id"]})]
    finally:
        db.close()
    assert positions == [0, 1]


def test_ducking_good_puts_the_latest_like_first(client, db_session_factory):
    _admin(client)
    one, two = (_make_track(db_session_factory, f"/nf/like-{name}.flac", title=name, artist="Liked First") for name in ("one", "two"))
    assert client.post("/api/playlists/liked-songs/tracks", json={"track_id": one}).status_code == 200
    assert client.post("/api/playlists/liked-songs/tracks", json={"track_id": two}).status_code == 200
    liked = next(p for p in client.get("/api/playlists").json() if p.get("system_key") == "liked_songs" or p["name"] in ("Ducking Good", "Loved Songs"))
    ids = _ids(client, liked["id"])
    assert ids.index(two) < ids.index(one)
    assert ids[0] == two


def test_existing_playlists_are_turned_over_once(client, db_session_factory):
    from app.db_migrations import turn_playlists_newest_first

    _admin(client)
    db = db_session_factory()
    try:
        tracks = [_make_track(db_session_factory, f"/nf/old-{i}.flac", title=f"Old {i}", artist="Old Order") for i in range(4)]
        playlist = client.post("/api/playlists", json={"name": "Old Order"}).json()
        # An old install's rows: appended, positions 0..3 in the order added.
        for position, track_id in enumerate(tracks):
            db.execute(text("insert into playlist_tracks (playlist_id, track_id, position) values (:p, :t, :pos)"), {"p": playlist["id"], "t": track_id, "pos": position})
        db.execute(text("update app_settings set playlists_newest_first = NULL"))
        db.commit()
    finally:
        db.close()

    turn_playlists_newest_first()
    assert _ids(client, playlist["id"]) == list(reversed(tracks))

    # Once. A second boot leaves the turned order alone.
    turn_playlists_newest_first()
    assert _ids(client, playlist["id"]) == list(reversed(tracks))
    db = db_session_factory()
    try:
        assert db.execute(text("select playlists_newest_first from app_settings")).scalar() in (1, True)
    finally:
        db.close()
