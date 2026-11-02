"""Pass 01 of the map work: tag weights and sources, the artist-first phase,
the weight backfill, and the two radio feedback fixes."""
from datetime import datetime, timedelta

import pytest

from tests.test_pass_p import _make_track


@pytest.fixture(autouse=True)
def _tidy_tracks(db_session_factory):
    """Every track made here has a path that does not exist, and the
    maintenance tests count exactly those. Take them away afterwards."""
    yield
    from app.models.artist_lastfm_check import ArtistLastfmCheck
    from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
    from app.models.track import Track
    from app.models.track_genre import TrackGenre

    db = db_session_factory()
    try:
        ids = [row.id for row in db.query(Track.id).filter(Track.file_path.like("/w/%") | Track.file_path.like("/ap/%") | Track.file_path.like("/bf/%"))]
        if ids:
            db.query(TrackGenre).filter(TrackGenre.track_id.in_(ids)).delete(synchronize_session=False)
            db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.query(ArtistLastfmCheck).filter(ArtistLastfmCheck.artist_key.like("phase %")).delete(synchronize_session=False)
        db.query(ArtistLastfmSimilarity).filter(ArtistLastfmSimilarity.source_artist_key == "phase gamma").delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_the_client_keeps_each_tags_count(monkeypatch):
    import app.services.lastfm as lastfm

    monkeypatch.setattr(lastfm, "_respect_lastfm_rate_limit", lambda: None)
    monkeypatch.setattr(
        lastfm.requests,
        "get",
        lambda *a, **k: _Response({"toptags": {"tag": [{"name": "metal", "count": 100}, {"name": "thrash metal", "count": "37"}, {"name": "seen live", "count": 5}, {"name": ""}]}}),
    )
    result = lastfm._request_lastfm({"method": "track.getTopTags"})
    assert result["success"] is True
    assert result["tags"] == ["metal", "thrash metal", "seen live"]
    assert result["tag_counts"] == {"metal": 100, "thrash metal": 37, "seen live": 5}

    monkeypatch.setattr(lastfm.requests, "get", lambda *a, **k: _Response({"error": 29, "message": "Rate limit exceeded"}, status=429))
    assert lastfm._request_lastfm_similar_artists({"method": "artist.getSimilar"}) == {
        "success": False, "artists": [], "error": "rate_limited", "rate_limited": True,
    }


def _api_key(db_session_factory):
    from app.models.app_setting import AppSetting

    db = db_session_factory()
    try:
        row = db.query(AppSetting).first()
        if row is None:
            row = AppSetting()
            db.add(row)
        row.lastfm_api_key = "k"
        db.commit()
    finally:
        db.close()


def test_enrichment_writes_weights_and_teaches_old_rows_theirs(client, db_session_factory, monkeypatch):
    import app.services.lastfm_enrichment as enrichment
    from app.models.track_genre import TrackGenre

    _api_key(db_session_factory)
    track_id = _make_track(db_session_factory, "/w/one.mp3", title="One", artist="Weighty", musicbrainz_recording_id="mb-w-1")
    db = db_session_factory()
    db.add(TrackGenre(track_id=track_id, genre="Metal"))  # written before weights existed
    db.add(TrackGenre(track_id=track_id, genre="Rock", source="file"))
    db.commit()
    db.close()

    monkeypatch.setattr(
        enrichment,
        "get_track_top_tags",
        lambda *a, **k: {"success": True, "tags": ["metal", "Thrash Metal", "seen live"], "tag_counts": {"metal": 100, "Thrash Metal": 41, "seen live": 9}},
    )
    db = db_session_factory()
    try:
        result = enrichment.enrich_track_lastfm_tags(db, track_id)
        assert result["success"], result
        rows = {row.genre.casefold(): row for row in db.query(TrackGenre).filter(TrackGenre.track_id == track_id)}
    finally:
        db.close()
    assert rows["metal"].weight == 100 and rows["metal"].source == "lastfm"  # the old row learnt its weight
    assert rows["thrash metal"].weight == 41 and rows["thrash metal"].source == "lastfm"  # new, weighted
    assert rows["rock"].weight is None and rows["rock"].source == "file"  # the file's tag is left alone
    assert "seen live" not in rows  # still filtered


def test_the_artist_phase_asks_once_for_every_library_artist(client, db_session_factory, monkeypatch):
    import app.services.lastfm_enrichment_batch as batch
    from app.models.artist_lastfm_check import ArtistLastfmCheck
    from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity

    _make_track(db_session_factory, "/ap/a.mp3", artist="Phase Alpha")
    _make_track(db_session_factory, "/ap/b.mp3", artist="Phase Beta")
    _make_track(db_session_factory, "/ap/c.mp3", artist="Phase Gamma")
    db = db_session_factory()
    db.add(ArtistLastfmSimilarity(source_artist_name="Phase Gamma", source_artist_key="phase gamma", similar_artist_name="X", similar_artist_key="x", match_score=0.5))
    db.commit()

    asked = []

    def fake_ingest(db, artist_name, limit):
        asked.append(artist_name)
        return {"success": True, "stored_count": 0 if artist_name == "Phase Beta" else 3}

    monkeypatch.setattr(batch, "ingest_similar_artists_for_artist", fake_ingest)
    first = batch.run_artist_similarity_phase(db)
    assert {name for name in asked if name.startswith("Phase")} == {"Phase Alpha", "Phase Beta"}  # Gamma already has rows
    assert first["artists_ingested"] >= 2 and first["stopped"] is None
    checks = {row.artist_key: row for row in db.query(ArtistLastfmCheck).filter(ArtistLastfmCheck.artist_key.like("phase %"))}
    assert checks["phase alpha"].similar_count == 3 and checks["phase beta"].similar_count == 0

    # Answered: not asked again tonight, even the one Last.fm had nothing for.
    asked.clear()
    batch.run_artist_similarity_phase(db)
    assert not [name for name in asked if name.startswith("Phase")]

    # A month on, the empty answer is worth another ask.
    checks["phase beta"].checked_at = datetime.utcnow() - timedelta(days=31)
    db.commit()
    asked.clear()
    batch.run_artist_similarity_phase(db)
    assert [name for name in asked if name.startswith("Phase")] == ["Phase Beta"]

    # A throttle backs off and gives up instead of hammering: five artists
    # due, five throttled answers, four waits, then it stops.
    asked.clear()
    checks["phase beta"].checked_at = datetime.utcnow() - timedelta(days=31)
    db.commit()
    for name in ("Delta", "Epsilon", "Zeta", "Eta"):
        _make_track(db_session_factory, f"/ap/{name}.mp3", artist=f"Phase {name}")
    assert len([key for key, _ in batch.artists_needing_similarity(db) if key.startswith("phase")]) == 5
    monkeypatch.setattr(batch, "ingest_similar_artists_for_artist", lambda db, artist_name, limit: {"success": False, "reason": "Rate Limit Exceeded"})
    slept = []
    monkeypatch.setattr(batch.time, "sleep", lambda s: slept.append(s))
    throttled = batch.run_artist_similarity_phase(db)
    assert throttled["stopped"] == "rate_limited" and len(slept) == batch.RATE_LIMIT_GIVE_UP_AFTER - 1
    db.close()


def test_the_weight_backfill_asks_again_and_labels_what_is_left(client, db_session_factory, monkeypatch):
    import app.services.lastfm_enrichment_batch as batch
    from app.models.track_genre import TrackGenre

    track_id = _make_track(db_session_factory, "/bf/one.mp3", artist="Backfill", musicbrainz_recording_id="mb-bf-1", lastfm_tags_enriched=True)
    done_id = _make_track(db_session_factory, "/bf/two.mp3", artist="Backfill", musicbrainz_recording_id="mb-bf-2", lastfm_tags_enriched=True)
    db = db_session_factory()
    db.add_all([
        TrackGenre(track_id=track_id, genre="Metal"),
        TrackGenre(track_id=track_id, genre="Obscure"),
        TrackGenre(track_id=done_id, genre="Metal", weight=90, source="lastfm"),
    ])
    db.commit()

    assert [t.id for t in batch.tracks_needing_tag_weights(db) if t.id in (track_id, done_id)] == [track_id]

    def fake_enrich(db, tid):
        row = db.query(TrackGenre).filter(TrackGenre.track_id == tid, TrackGenre.genre == "Metal").one()
        row.weight, row.source = 100, "lastfm"
        db.commit()
        return {"success": True}

    monkeypatch.setattr(batch, "enrich_track_lastfm_tags", fake_enrich)
    result = batch.run_tag_weight_backfill(db)
    assert result["tracks_weighted"] >= 1
    rows = {row.genre: row for row in db.query(TrackGenre).filter(TrackGenre.track_id == track_id)}
    assert rows["Metal"].weight == 100 and rows["Metal"].source == "lastfm"
    assert rows["Obscure"].weight is None and rows["Obscure"].source == "legacy"
    assert not [t.id for t in batch.tracks_needing_tag_weights(db) if t.id == track_id]
    db.close()
