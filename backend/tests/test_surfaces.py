"""Every read surface the web UI stands on, swept on both engines.

Born from a real regression: the genres listing used DISTINCT + ORDER BY
lower(), legal on SQLite and refused by Postgres — and because the frontend
loads artists/albums/genres/counts in one Promise.all, that single 500
emptied the sidebar stats and three whole pages. The smoke tests never hit
those endpoints, so the migration shipped with it.

This file's contract: every GET the UI's pages depend on answers 200 with
believable content, against seeded data that exercises artists, genres,
albums, likes and listening history alike.
"""

import pytest


@pytest.fixture(scope="module")
def surface_client(client, db_session_factory):
    """Signed-in client plus a seeded library slice.

    Tracks get real TrackArtist and TrackGenre rows — the artists and genres
    listings read those tables, not the columns on tracks — and a listening
    event plus a like feed the stats endpoints.
    """
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre

    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )
    assert login.status_code == 200

    db = db_session_factory()
    try:
        existing = (
            db.query(Track).filter(Track.title == "Surface Song 1").first()
        )
        if not existing:
            for index in (1, 2):
                track = Track(
                    title=f"Surface Song {index}",
                    artist="Surface Artist",
                    album="Surface Album",
                    genre="Surfacewave",
                    file_path=f"/nonexistent/surface-{index}.mp3",
                    duration_seconds=180 + index,
                )
                db.add(track)
                db.flush()
                db.add(
                    TrackArtist(
                        track_id=track.id, artist_name="Surface Artist", position=0
                    )
                )
                db.add(TrackGenre(track_id=track.id, genre="Surfacewave"))
            db.commit()

        track_id = (
            db.query(Track.id).filter(Track.title == "Surface Song 1").scalar()
        )
    finally:
        db.close()

    client.post(
        "/api/listening-events",
        json={
            "track_id": track_id,
            "event_type": "play_started",
            "source_type": "library",
        },
    )
    client.post("/api/playlists/liked-songs/tracks", json={"track_id": track_id})

    return client, track_id


def test_library_listings_feed_the_sidebar_and_pages(surface_client):
    client, _ = surface_client

    artists = client.get("/api/artists")
    assert artists.status_code == 200
    assert "Surface Artist" in artists.json()

    albums = client.get("/api/albums")
    assert albums.status_code == 200
    assert "Surface Album" in albums.json()

    genres = client.get("/api/genres")
    assert genres.status_code == 200
    assert "Surfacewave" in genres.json()

    count = client.get("/api/tracks/count")
    assert count.status_code == 200
    assert count.json()["count"] >= 2

    for path in ("/api/albums/artwork", "/api/artists/artwork"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_entity_pages(surface_client):
    client, track_id = surface_client

    artist_tracks = client.get("/api/artists/Surface Artist/tracks")
    assert artist_tracks.status_code == 200

    album_tracks = client.get("/api/albums/Surface Album/tracks")
    assert album_tracks.status_code == 200

    genre_tracks = client.get("/api/genres/Surfacewave/tracks")
    assert genre_tracks.status_code == 200

    artist_genres = client.get("/api/artists/Surface Artist/genres")
    assert artist_genres.status_code == 200

    similar = client.get(f"/api/tracks/{track_id}/similar")
    assert similar.status_code == 200


INSIGHTS_ENDPOINTS = [
    "/api/stats/summary",
    "/api/stats/plays-over-time",
    "/api/stats/top-artists",
    "/api/stats/top-albums",
    "/api/stats/by-source",
    "/api/stats/by-hour",
    "/api/stats/overview",
    "/api/stats/top-played",
    "/api/stats/most-liked",
    "/api/stats/recently-played",
    "/api/stats/most-skipped",
]


@pytest.mark.parametrize("path", INSIGHTS_ENDPOINTS)
def test_insights_surface(surface_client, path):
    client, _ = surface_client

    response = client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code}"


def test_insights_daily_buckets_carry_todays_play(surface_client):
    """plays-over-time uses the dialect-specific local-day bucketing; the
    event recorded moments ago must land on today's row on both engines."""
    from datetime import date

    client, _ = surface_client

    response = client.get("/api/stats/plays-over-time", params={"days": 7})
    assert response.status_code == 200
    rows = {row["date"]: row["plays"] for row in response.json()}
    assert rows.get(date.today().isoformat(), 0) >= 1

    summary = client.get("/api/stats/summary")
    assert summary.status_code == 200


def test_home_rails(surface_client):
    client, _ = surface_client

    for_you = client.get("/api/recommendations/for-you")
    assert for_you.status_code == 200
