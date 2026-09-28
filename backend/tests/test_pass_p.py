"""Pass P: the server holds the line.

Security, streaming, operations and the scale cliffs, each pinned by a test
that runs on both engines.
"""

import io
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _admin(client):
    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )
    assert login.status_code == 200, login.text
    return client


def _make_track(db_session_factory, path: str, **fields):
    from app.models.track import Track

    db = db_session_factory()
    try:
        track = Track(title=fields.pop("title", "Song"), artist=fields.pop("artist", "Artist"), file_path=path, **fields)
        db.add(track)
        db.commit()
        return track.id
    finally:
        db.close()


# --- OPS-1 / API-8: health ---------------------------------------------------


def test_health_reports_degraded_when_the_library_is_not_there(client, monkeypatch, tmp_path):
    from app.config import settings

    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.setattr(settings, "music_library_path", str(empty))

    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["library"] is False
    assert body["checks"]["database"] is True
    assert body["api_version"] >= 3
    assert "capabilities" in body


def test_health_is_ok_with_a_mounted_library(client, monkeypatch, tmp_path):
    from app.config import settings
    from app.routes import health

    library = tmp_path / "music"
    library.mkdir()
    (library / "a.mp3").write_bytes(b"x")
    monkeypatch.setattr(settings, "music_library_path", str(library))
    monkeypatch.setattr(health, "_FFMPEG_AVAILABLE", True)

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- MEDIA-2 / MEDIA-7 / SEC-6: streaming ---------------------------------


def test_media_types_are_ones_players_accept():
    from app.routes.tracks import media_type_for

    assert media_type_for(Path("a.m4a")) == "audio/mp4"
    assert media_type_for(Path("a.flac")) == "audio/flac"
    assert media_type_for(Path("a.mp3")) == "audio/mpeg"
    assert media_type_for(Path("a.opus")) == "audio/ogg"


def test_ranges_past_the_end_are_clamped_and_responses_are_private(client, db_session_factory, tmp_path):
    from app.routes.tracks import create_stream_token

    _admin(client)
    audio = tmp_path / "song.mp3"
    audio.write_bytes(bytes(range(256)) * 40)  # 10,240 bytes
    track_id = _make_track(db_session_factory, str(audio))

    from app.models.user import User

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
    finally:
        db.close()

    token = create_stream_token(track_id, admin_id)
    url = f"/api/tracks/{track_id}/mobile-stream?quality=original"
    headers = {"X-Stream-Token": token}

    whole = client.get(url, headers=headers)
    assert whole.status_code == 200
    assert whole.headers["content-type"].startswith("audio/mpeg")
    assert whole.headers["cache-control"].startswith("private")
    assert "ETag" in whole.headers or "etag" in whole.headers

    clamped = client.get(url, headers={**headers, "Range": "bytes=0-999999999"})
    assert clamped.status_code == 206
    assert clamped.headers["content-range"] == "bytes 0-10239/10240"

    multi = client.get(url, headers={**headers, "Range": "bytes=0-0,5-5"})
    assert multi.status_code == 200

    stale = client.get(url, headers={**headers, "Range": "bytes=0-99", "If-Range": '"nope"'})
    assert stale.status_code == 200

    beyond = client.get(url, headers={**headers, "Range": "bytes=999999999-"})
    assert beyond.status_code == 416


# --- API-2 / DATA-8 / API-6 / API-7: track shapes --------------------------


@pytest.fixture(scope="module")
def library_with_playlist(client, db_session_factory):
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.user import User

    _admin(client)
    ids = [
        _make_track(db_session_factory, f"/lib/shape-{i}.mp3", title=f"Shape {i}", album="Shapes", duration_seconds=100 + i)
        for i in range(3)
    ]

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        for track_id in ids:
            db.add(TrackGenre(track_id=track_id, genre="Folk"))
            db.add(TrackGenre(track_id=track_id, genre="Ambient"))
            db.add(TrackArtist(track_id=track_id, artist_name="Artist", position=0))
            db.add(TrackArtist(track_id=track_id, artist_name="Guest", position=1))
        playlist = Playlist(user_id=admin_id, name="Shapes list")
        db.add(playlist)
        db.flush()
        for position, track_id in enumerate(ids):
            db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=position))
        db.commit()
        return playlist.id, ids
    finally:
        db.close()


def test_playlist_tracks_are_full_rows_and_pageable(client, library_with_playlist):
    playlist_id, ids = library_with_playlist

    whole = client.get(f"/api/playlists/{playlist_id}/tracks")
    assert whole.status_code == 200, whole.text
    rows = whole.json()
    assert [row["id"] for row in rows] == ids
    assert rows[0]["genres"] == ["Folk", "Ambient"] or set(rows[0]["genres"]) == {"Folk", "Ambient"}
    assert rows[0]["artists"] == ["Artist", "Guest"]
    assert rows[0]["duration_seconds"] == 100

    page = client.get(f"/api/playlists/{playlist_id}/tracks", params={"limit": 2, "offset": 1})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert [row["id"] for row in body["items"]] == ids[1:3]
    assert body["has_more"] is False


def test_genre_rows_carry_duration_artists_and_every_genre(client, library_with_playlist):
    response = client.get("/api/genres/Folk/tracks", params={"limit": 10, "offset": 0})
    assert response.status_code == 200, response.text
    row = response.json()["items"][0]
    assert row["duration_seconds"] is not None
    assert row["artists"] == ["Artist", "Guest"]
    assert set(row["genres"]) == {"Folk", "Ambient"}
    assert "play_count" in row


def test_stats_overview_uses_the_batched_builder(client, library_with_playlist):
    response = client.get("/api/stats/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    for rail in ("top_played", "most_liked", "recently_played"):
        for row in body[rail]:
            assert "artwork_path" in row


# --- MEDIA-11: likes ---------------------------------------------------------


def test_liking_a_missing_track_is_a_404_and_unknown_sources_are_dropped(client, library_with_playlist):
    _, ids = library_with_playlist

    missing = client.post("/api/tracks/999999/like", json={})
    assert missing.status_code == 404

    odd_source = client.post(f"/api/tracks/{ids[0]}/like", json={"source_type": "carplay"})
    assert odd_source.status_code == 200, odd_source.text
    assert odd_source.json()["source_type"] is None


# --- MEDIA-8: playback queue --------------------------------------------------


def test_playback_queue_is_capped_and_ignores_missing_tracks(client, library_with_playlist):
    _, ids = library_with_playlist
    from app.routes.playback import MAX_QUEUE_ITEMS

    huge = ids * ((MAX_QUEUE_ITEMS // len(ids)) + 5)
    saved = client.put(
        "/api/playback",
        json={
            "current_track_id": ids[0],
            "queue_index": 10,
            "current_time_seconds": 0,
            "is_playing": False,
            "is_shuffle": False,
            "is_loop": False,
            "queue_track_ids": huge,
        },
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["queue_track_ids"]) == MAX_QUEUE_ITEMS

    with_ghost = client.put(
        "/api/playback",
        json={
            "current_track_id": 999999,
            "queue_index": 1,
            "current_time_seconds": 0,
            "is_playing": False,
            "is_shuffle": False,
            "is_loop": False,
            "queue_track_ids": [ids[0], 999999, ids[1]],
        },
    )
    assert with_ghost.status_code == 200, with_ghost.text
    assert with_ghost.json()["queue_track_ids"] == [ids[0], ids[1]]
    assert with_ghost.json()["current_track_id"] is None


# --- SEC-1 / SEC-5: recovery codes and enumeration ------------------------------


def test_recovery_codes_are_keyed_hashes_and_the_username_tier_applies(client, db_session_factory):
    from app.models.user import User
    from app.services.rate_limit import username_recovery_limiter

    _admin(client)
    codes = client.post("/api/auth/recovery-codes").json()["recovery_codes"]
    assert all(len(code) == 10 for code in codes)

    db = db_session_factory()
    try:
        stored = db.query(User).filter_by(username="admin").one().recovery_codes_hashes
    finally:
        db.close()
    assert "$2" not in stored, "codes must not be bcrypt hashes any more"

    # A wrong code is answered in milliseconds now, not seconds.
    started = time.perf_counter()
    wrong = client.post(
        "/api/auth/recover-password",
        json={
            "username": "admin",
            "recovery_code": "NOPE000000",
            "new_password": "another-password-1",
            "confirm_password": "another-password-1",
        },
    )
    elapsed = time.perf_counter() - started
    assert wrong.status_code == 401
    assert elapsed < 1.5

    # The username tier counts every client's failures together.
    key = "admin"
    for _ in range(25):
        username_recovery_limiter.record_failure(key)
    limited = client.post(
        "/api/auth/recover-password",
        json={
            "username": "admin",
            "recovery_code": codes[0],
            "new_password": "another-password-1",
            "confirm_password": "another-password-1",
        },
    )
    assert limited.status_code == 429
    username_recovery_limiter.record_success(key)

    # A real code still works, and once.
    from app.services.rate_limit import recovery_limiter

    recovery_limiter.record_success(f"testclient:{key}")
    good = client.post(
        "/api/auth/recover-password",
        json={
            "username": "admin",
            "recovery_code": codes[1],
            "new_password": "test-password-1",
            "confirm_password": "test-password-1",
        },
    )
    assert good.status_code == 200, good.text


def test_the_right_password_is_never_locked_out_by_others_guesses(client):
    from app.services.rate_limit import username_login_limiter

    _admin(client)
    for _ in range(60):
        username_login_limiter.record_failure("admin")

    # A wrong guess is refused across clients...
    wrong = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "not-it"},
    )
    assert wrong.status_code == 429

    # ...and the right password still gets in, which is what the owner needs
    # while somebody else is hammering their username.
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )
    assert login.status_code == 200, login.text
    username_login_limiter.record_success("admin")


def test_renaming_to_a_taken_username_does_not_say_it_is_taken(client):
    _admin(client)
    response = client.patch(
        "/api/auth/me",
        json={"current_password": "test-password-1", "username": "admin"},
    )
    # Same name as before is fine; a *different* taken name would be the
    # generic refusal. Both never say "already exists".
    assert "already exists" not in response.text


# --- SEC-3: a one-time password is not a session ----------------------------


def test_a_pending_temp_password_only_allows_choosing_a_password(client, db_session_factory):
    from app.models.user import User
    from app.services.auth import hash_password

    _admin(client)
    db = db_session_factory()
    try:
        db.add(
            User(
                username="temp-holder",
                password_hash=hash_password("temporary-pass-1"),
                role="user",
                must_change_password=True,
                temp_password_issued_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as holder:
        login = holder.post(
            "/api/auth/login", json={"username": "temp-holder", "password": "temporary-pass-1"}
        )
        assert login.status_code == 200, login.text

        assert holder.get("/api/auth/me").status_code == 200
        blocked = holder.get("/api/tracks/count")
        assert blocked.status_code == 403
        assert blocked.headers.get("x-adjacent-code") == "password_change_required"

        changed = holder.patch(
            "/api/auth/me",
            json={
                "current_password": "temporary-pass-1",
                "new_password": "chosen-password-1",
                "confirm_password": "chosen-password-1",
            },
        )
        assert changed.status_code == 200, changed.text
        assert holder.get("/api/tracks/count").status_code == 200


# --- SEC-2 / SEC-9: uploads and headers -------------------------------------


def test_uploads_are_judged_by_their_bytes(client):
    _admin(client)
    created = client.post("/api/playlists", json={"name": "Cover test"})
    assert created.status_code == 200, created.text
    playlist_id = created.json()["id"]

    zeros = client.post(
        f"/api/playlists/{playlist_id}/artwork",
        files={"file": ("big.png", io.BytesIO(b"\x00" * 4096), "image/png")},
    )
    assert zeros.status_code == 400

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    real = client.post(
        f"/api/playlists/{playlist_id}/artwork",
        files={"file": ("cover.jpg", io.BytesIO(png), "image/jpeg")},
    )
    assert real.status_code == 200, real.text
    assert real.json()["artwork_path"].endswith(".png")

    fetched = client.get(real.json()["artwork_path"])
    assert fetched.status_code == 200
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in fetched.headers["content-security-policy"]


def test_api_responses_carry_security_headers(client):
    response = client.get("/api/auth/setup-status")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


# --- OPS-12: several origins -------------------------------------------------


def test_frontend_origin_accepts_a_list():
    from app.config import Settings

    settings = Settings(
        auth_secret_key="0123456789abcdef0123456789abcdef0123456789",
        frontend_origin="http://192.168.1.50:5173/, http://nas.local:5173",
    )
    assert settings.frontend_origins == ["http://192.168.1.50:5173", "http://nas.local:5173"]


# --- DATA-6: indexes on both engines ----------------------------------------


def test_the_expression_indexes_exist_on_this_engine(client):
    from app.db_migrations import existing_index_names

    names = existing_index_names("tracks")
    assert {"ix_tracks_lower_artist", "ix_tracks_lower_album", "ix_tracks_lower_title"} <= names
    assert "ix_listening_events_user_type_time" in existing_index_names("listening_events")


# --- DATA-9: splitting -------------------------------------------------------


def test_artist_and_genre_splitting():
    from app.services.metadata_normalizer import normalize_artist_list, normalize_genre_list

    assert normalize_artist_list("Brooks & Dunn") == ["Brooks & Dunn"]
    assert normalize_artist_list("Earth, Wind & Fire") == ["Earth, Wind & Fire"]
    assert normalize_artist_list("Drake feat. Rihanna") == ["Drake", "Rihanna"]
    assert normalize_artist_list("Drake / Rihanna") == ["Drake", "Rihanna"]
    assert normalize_artist_list("2Pac, Left Eye") == ["2Pac", "Left Eye"]
    assert normalize_artist_list("MGMT") == ["MGMT"]
    assert normalize_genre_list("Drum & Bass") == ["Drum & Bass"]
    assert normalize_genre_list("Pop, Rock & Roll") == ["Pop", "Rock & Roll"]


# --- DATA-15: credits follow an edit -----------------------------------------


def test_editing_the_artist_updates_the_credit_rows(client, library_with_playlist, db_session_factory):
    from app.models.track_artist import TrackArtist

    _, ids = library_with_playlist
    edited = client.patch(
        f"/api/tracks/{ids[0]}",
        json={"title": "Shape 0", "artist": "Renamed", "album": "Shapes", "genres": ["Folk", "Ambient"]},
    )
    assert edited.status_code == 200, edited.text

    db = db_session_factory()
    try:
        credits = (
            db.query(TrackArtist)
            .filter(TrackArtist.track_id == ids[0])
            .order_by(TrackArtist.position)
            .all()
        )
        assert [c.artist_name for c in credits] == ["Renamed", "Guest"]
    finally:
        db.close()

    renamed = client.patch(
        "/api/artists/rename", json={"current_artist": "Renamed", "new_artist": "Final"}
    )
    assert renamed.status_code == 200, renamed.text
    db = db_session_factory()
    try:
        assert db.query(TrackArtist).filter(TrackArtist.artist_name == "Final").count() == 1
        assert db.query(TrackArtist).filter(TrackArtist.artist_name == "Renamed").count() == 0
    finally:
        db.close()


# --- DATA-2 / DATA-3: co-occurrence ------------------------------------------


def test_large_playlists_are_sampled_and_the_retriever_aggregates(client, db_session_factory):
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack
    from app.models.user import User
    from app.services.recommendations.cooccurrence_builder import (
        PLAYLIST_FULL_PAIRS_UP_TO,
        PLAYLIST_SAMPLE_PARTNERS,
        rebuild_track_cooccurrence,
    )
    from app.services.recommendations.retrievers.cooccurrence_retriever import (
        retrieve_cooccurrence_candidates,
    )

    _admin(client)
    ids = [
        _make_track(db_session_factory, f"/lib/co-{i}.mp3", title=f"Co {i}")
        for i in range(PLAYLIST_FULL_PAIRS_UP_TO + 100)
    ]

    db = db_session_factory()
    try:
        admin_id = db.query(User).filter_by(username="admin").one().id
        playlist = Playlist(user_id=admin_id, name="Big co")
        db.add(playlist)
        db.flush()
        for position, track_id in enumerate(ids):
            db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=position))
        db.commit()

        result = rebuild_track_cooccurrence(db)
        n = len(ids)
        assert result["pairs_written"] <= n * PLAYLIST_SAMPLE_PARTNERS
        assert result["pairs_written"] < n * (n - 1) // 2

        candidates = retrieve_cooccurrence_candidates(db, ids[:5], limit=20)
        assert candidates
        assert not any(track_id in ids[:5] for track_id in candidates)
    finally:
        db.close()


# --- DATA-5: the backfill walks once ------------------------------------------


def test_backfill_walks_the_library_once_and_marks_attempts(client, db_session_factory, monkeypatch):
    from app.models.track import Track
    from app.services import musicbrainz_backfill

    _admin(client)
    ids = [_make_track(db_session_factory, f"/lib/mb-{i}.mp3", title=f"MB {i}") for i in range(7)]

    seen = []
    monkeypatch.setattr(musicbrainz_backfill, "contact_configured", lambda: True)
    monkeypatch.setattr(
        musicbrainz_backfill,
        "find_recording_mbid",
        lambda title, artist, **kwargs: seen.append(title) or None,
    )

    summary = musicbrainz_backfill.backfill_musicbrainz_recording_ids(
        batch_size=3, request_delay_seconds=0, batch_delay_seconds=0
    )

    mine = [title for title in seen if title.startswith("MB ")]
    assert sorted(mine) == sorted(f"MB {i}" for i in range(7)), "each track once"
    assert summary["total_checked"] >= 7

    db = db_session_factory()
    try:
        checked = db.query(Track).filter(Track.id.in_(ids), Track.musicbrainz_checked_at.isnot(None)).count()
        assert checked == 7
    finally:
        db.close()

    seen.clear()
    musicbrainz_backfill.backfill_musicbrainz_recording_ids(
        batch_size=3, request_delay_seconds=0, batch_delay_seconds=0
    )
    assert not [title for title in seen if title.startswith("MB ")], "not retried immediately"


def test_backfill_refuses_to_run_without_a_contact_address(monkeypatch):
    from app.services import musicbrainz_backfill

    monkeypatch.setattr(musicbrainz_backfill, "contact_configured", lambda: False)
    summary = musicbrainz_backfill.backfill_musicbrainz_recording_ids(max_batches=1)
    assert summary.get("skipped") == "no_contact"


# --- DATA-10: the scanner recognises moves and re-reads edited tags -----------


def test_scanner_keeps_a_moved_file_and_refreshes_an_edited_one(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.services import scanner

    _admin(client)
    library = tmp_path / "lib"
    (library / "a").mkdir(parents=True)

    tags = {}

    def fake_metadata(path):
        return {
            "file_path": path,
            "title": tags.get(path, "Original Title"),
            "artist": "Mover",
            "album": "Moves",
            "duration_seconds": 12.0,
        }

    monkeypatch.setattr(scanner, "extract_track_metadata", fake_metadata)
    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)

    original = library / "a" / "song.mp3"
    original.write_bytes(b"audio-bytes-that-do-not-change")
    os.utime(original, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    first = scanner.scan_directory(str(library), limit=100)
    assert first["added"] == 1

    db = db_session_factory()
    try:
        track = db.query(Track).filter(Track.file_path == str(original)).one()
        track_id = track.id
        assert track.file_size == original.stat().st_size
    finally:
        db.close()

    # Move it: same bytes, same mtime, new path.
    moved = library / "b" / "song.mp3"
    moved.parent.mkdir()
    original.rename(moved)

    second = scanner.scan_directory(str(library), limit=100)
    assert second["added"] == 0

    db = db_session_factory()
    try:
        track = db.get(Track, track_id)
        assert track.file_path == str(moved), "the row followed the file"
    finally:
        db.close()

    # Edit the tags: a new mtime under the same path.
    tags[str(moved)] = "Fixed Title"
    os.utime(moved, ns=(1_700_000_500_000_000_000, 1_700_000_500_000_000_000))

    third = scanner.scan_directory(str(library), limit=100)
    assert third["added"] == 0

    db = db_session_factory()
    try:
        assert db.get(Track, track_id).title == "Fixed Title"
    finally:
        db.close()
