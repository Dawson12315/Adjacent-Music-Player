"""End-to-end smoke of the API surface, engine-agnostic.

One sequential story through the core flows — first-run setup, auth, the
per-user playlist/like model, listening stats — asserted identically on
SQLite and PostgreSQL. Anything dialect-specific that drifts between the two
engines should fail here first.
"""


def test_setup_status_reports_admin_presence(client):
    response = client.get("/api/auth/setup-status")
    assert response.status_code == 200
    assert isinstance(response.json().get("admin_exists"), bool)


def test_admin_bootstrap_or_login_signs_in(client):
    """Order-independent: the migration tests may already have bootstrapped
    the admin (with the same credentials); either path must end signed in."""
    response = client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )

    if response.status_code != 200:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-password-1"},
        )
        assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_wrong_password_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_playlists_are_scoped_and_system_playlist_is_ensured(client):
    created = client.post("/api/playlists", json={"name": "Smoke Test"})
    assert created.status_code == 200

    liked = client.get("/api/playlists/liked-songs")
    assert liked.status_code == 200
    assert liked.json()["is_system"] is True

    listing = client.get("/api/playlists")
    assert listing.status_code == 200
    names = {playlist["name"] for playlist in listing.json()}
    assert "Smoke Test" in names


def test_like_flow_and_track_listing(client, db_session_factory):
    # A track inserted directly — the scanner needs real audio files and has
    # its own coverage; this story is about everything downstream of it.
    from app.models.track import Track

    db = db_session_factory()
    try:
        track = Track(
            title="Smoke Song",
            artist="Smoke Artist",
            album="Smoke Album",
            genre="Electronic",
            file_path="/nonexistent/smoke.mp3",
            duration_seconds=180,
        )
        db.add(track)
        db.commit()
        track_id = track.id
    finally:
        db.close()

    listing = client.get("/api/tracks", params={"limit": 10})
    assert listing.status_code == 200
    payload = listing.json()
    items = payload["items"] if isinstance(payload, dict) else payload
    assert any(item["id"] == track_id for item in items)

    liked = client.post(
        "/api/playlists/liked-songs/tracks", json={"track_id": track_id}
    )
    assert liked.status_code == 200

    is_liked = client.get(f"/api/playlists/liked-songs/tracks/{track_id}")
    assert is_liked.status_code == 200
    assert is_liked.json() == {"liked": True}


def test_listening_event_lands_in_local_hour_bucket(client):
    listing = client.get("/api/tracks", params={"limit": 1})
    payload = listing.json()
    items = payload["items"] if isinstance(payload, dict) else payload
    track_id = items[0]["id"]

    recorded = client.post(
        "/api/listening-events",
        json={
            "track_id": track_id,
            "event_type": "play_started",
            "source_type": "library",
        },
    )
    assert recorded.status_code == 200

    # The dialect-specific query: strftime on SQLite, timezone()+to_char on
    # Postgres. Both must bucket a just-now event into the current local hour.
    from datetime import datetime

    by_hour = client.get("/api/stats/by-hour")
    assert by_hour.status_code == 200
    rows = by_hour.json()
    assert len(rows) == 24
    plays = {row["hour"]: row["plays"] for row in rows}
    assert plays[datetime.now().hour] >= 1


def test_second_user_cannot_be_bootstrapped_twice(client):
    response = client.post(
        "/api/auth/setup-admin",
        json={"username": "intruder", "password": "whatever-password-1"},
    )
    assert response.status_code in (400, 403, 409)
