"""Playlist rows are indexed, one per (playlist, track)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db_migrations import dedupe_playlist_tracks, existing_index_names, sync_model_indexes
from tests.test_pass_p import _admin, _make_track


def test_the_indexes_exist_on_this_engine(client):
    names = existing_index_names("playlist_tracks")
    assert {"ix_playlist_tracks_pair", "ix_playlist_tracks_track_id"} <= names


def test_a_duplicate_pair_is_refused_by_the_database(client, db_session_factory):
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack

    _admin(client)
    track_id = _make_track(db_session_factory, "/lib/pt-dup.flac", title="Dup")
    db = db_session_factory()
    try:
        playlist = Playlist(name="Pair test", user_id=1)
        db.add(playlist)
        db.flush()
        db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=0))
        db.flush()
        db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=1))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    finally:
        db.close()


def test_the_route_answers_400_to_a_second_add(client, db_session_factory):
    _admin(client)
    track_id = _make_track(db_session_factory, "/lib/pt-route.flac", title="Route")
    playlist_id = client.post("/api/playlists", json={"name": "Route test"}).json()["id"]
    first = client.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id})
    assert first.status_code in (200, 201), first.text
    second = client.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id})
    assert second.status_code == 400


def test_dedupe_keeps_the_earliest_row(client, db_session_factory):
    """An older file may hold a pair twice; the index cannot be built over it
    until the extras go. Simulated by dropping the index, inserting, and
    running the one-time dedupe and the sync again."""
    from sqlalchemy import text

    from app.db import engine
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack

    _admin(client)
    track_id = _make_track(db_session_factory, "/lib/pt-dedupe.flac", title="Dedupe")
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_playlist_tracks_pair"))
    db = db_session_factory()
    try:
        playlist = Playlist(name="Dedupe test", user_id=1)
        db.add(playlist)
        db.flush()
        for position in (0, 1, 2):
            db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=position))
        db.commit()
        playlist_id = playlist.id
    finally:
        db.close()

    dedupe_playlist_tracks()
    sync_model_indexes()

    db = db_session_factory()
    try:
        rows = db.query(PlaylistTrack).filter_by(playlist_id=playlist_id).all()
        assert len(rows) == 1 and rows[0].position == 0
    finally:
        db.close()
    assert "ix_playlist_tracks_pair" in existing_index_names("playlist_tracks")
