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


def test_playlists_carry_a_track_count_and_an_album_preview(surface_client, db_session_factory):
    """A playlist row on a client shows its size and a mosaic of its albums.

    The count and the preview come with the listing, so a Playlists page or a
    car screen never has to open every playlist to describe it.
    """
    from app.models.track import Track

    client, _ = surface_client

    created = client.post("/api/playlists", json={"name": "Surface Mix"})
    assert created.status_code == 200
    assert created.json()["track_count"] == 0
    assert created.json()["preview"] == []
    playlist_id = created.json()["id"]

    db = db_session_factory()
    try:
        track_ids = [
            row.id
            for row in db.query(Track.id)
            .filter(Track.title.in_(["Surface Song 1", "Surface Song 2"]))
            .order_by(Track.title.asc())
            .all()
        ]
    finally:
        db.close()
    assert len(track_ids) == 2

    for track_id in track_ids:
        added = client.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id})
        assert added.status_code == 200, added.text

    listing = client.get("/api/playlists")
    assert listing.status_code == 200
    by_id = {playlist["id"]: playlist for playlist in listing.json()}

    mix = by_id[playlist_id]
    assert mix["track_count"] == 2
    # Two tracks from one album make one preview tile, in playlist order.
    assert mix["preview"] == [
        {"title": "Surface Song 1", "album": "Surface Album", "artwork_path": None}
    ]

    # Ducking Good holds whatever earlier tests liked as well; the fixture's
    # like is in there, and so is its album.
    liked = next(playlist for playlist in listing.json() if playlist["system_key"])
    assert liked["track_count"] >= 1
    assert any(item["album"] == "Surface Album" for item in liked["preview"])

    # The single-playlist routes describe a playlist the same way.
    renamed = client.patch(f"/api/playlists/{playlist_id}", json={"name": "Surface Mix 2"})
    assert renamed.status_code == 200
    assert renamed.json()["track_count"] == 2
    assert [item["title"] for item in renamed.json()["preview"]] == ["Surface Song 1"]
