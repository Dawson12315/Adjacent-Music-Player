"""The map: where artists and tracks sit, and how the recommender and radio
read it. A small library with two metal acts, a pop act, and an act with no
tags at all that Last.fm says is near one of the metal acts."""
import numpy as np
import pytest

from tests.test_pass_p import _make_track
from tests.test_track_numbers_and_dismissals import _credit


def _tags(db_session_factory, track_ids, tags):
    from app.models.track_genre import TrackGenre

    db = db_session_factory()
    try:
        for track_id in track_ids:
            for genre, weight in tags:
                db.add(TrackGenre(track_id=track_id, genre=genre, weight=weight, source="lastfm"))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def map_library(client, db_session_factory):
    from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
    from app.models.track_cooccurrence import TrackCooccurrence
    from app.models.track_lastfm_similarity import TrackLastfmSimilarity
    from app.services.recommendations.rec_cache import invalidate_library_caches

    def act(name, album, n=3):
        ids = [_make_track(db_session_factory, f"/map/{name}-{i}.flac", title=f"{name} {i}", artist=name, album=album, track_number=i + 1) for i in range(n)]
        _credit(db_session_factory, ids, name)
        return ids

    thrash = act("Map Thrash", "Ride the Map")
    heavy = act("Map Heavy", "Heavy Map")
    pop = act("Map Pop", "Pop Map")
    mute = act("Map Mute", "Mute Map")  # no tags at all
    _tags(db_session_factory, thrash, [("Metal", 100), ("Thrash Metal", 80), ("Rock", 20)])
    _tags(db_session_factory, heavy, [("Metal", 100), ("Heavy Metal", 70), ("Thrash Metal", 40), ("Rock", 30)])
    _tags(db_session_factory, pop, [("Pop", 100), ("Dance Pop", 60)])
    db = db_session_factory()
    try:
        db.add(ArtistLastfmSimilarity(source_artist_name="Map Thrash", source_artist_key="map thrash", similar_artist_name="Map Mute", similar_artist_key="map mute", match_score=0.8))
        db.add(TrackLastfmSimilarity(source_track_id=thrash[0], similar_track_id=heavy[0], source_track_name="a", source_artist_name="Map Thrash", similar_track_name="b", similar_artist_name="Map Heavy", source_track_key="k1", similar_track_key="k2", match_score=0.9))
        db.add(TrackCooccurrence(track_a_id=mute[1], track_b_id=heavy[1], cooccurrence_count=6))
        db.commit()
    finally:
        db.close()
    invalidate_library_caches()
    yield {"thrash": thrash, "heavy": heavy, "pop": pop, "mute": mute, "all": thrash + heavy + pop + mute}

    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.track_vector import TrackVector

    db = db_session_factory()
    try:
        ids = thrash + heavy + pop + mute
        for model in (TrackVector, TrackArtist, TrackGenre):
            db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(TrackLastfmSimilarity).filter(TrackLastfmSimilarity.source_track_id.in_(ids)).delete(synchronize_session=False)
        db.query(TrackCooccurrence).filter(TrackCooccurrence.track_a_id.in_(ids)).delete(synchronize_session=False)
        db.query(ArtistLastfmSimilarity).filter(ArtistLastfmSimilarity.source_artist_key == "map thrash").delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    invalidate_library_caches()


def _cos(a, b):
    return float(np.dot(a, b))


def test_the_map_puts_like_with_like_and_places_the_untagged_by_their_neighbours(db_session_factory, map_library):
    from app.services.recommendations import vector_map

    db = db_session_factory()
    try:
        summary = vector_map.rebuild_vector_map(db)
        assert summary["artists_placed"] >= 4 and summary["tracks_placed"] >= 12, summary
        assert summary["dimensions"] >= 2
        index = vector_map.get_vector_index(db)
    finally:
        db.close()
    assert index is not None
    thrash, heavy, pop, mute = (index.artist_vector(k) for k in ("map thrash", "map heavy", "map pop", "map mute"))
    assert all(v is not None for v in (thrash, heavy, pop, mute))
    # Two metal acts are nearer each other than either is to pop.
    assert _cos(thrash, heavy) > _cos(thrash, pop) + 0.2
    assert _cos(heavy, thrash) > _cos(heavy, pop) + 0.2
    # The act with no tags sits by the act Last.fm paired it with, not by pop.
    assert _cos(mute, thrash) > _cos(mute, pop)
    # Tracks inherit their artist; every track is placed, unit length.
    for track_id in map_library["all"]:
        vector = index.vector_of(track_id)
        assert vector is not None and abs(float(np.linalg.norm(vector)) - 1.0) < 1e-4
    assert _cos(index.vector_of(map_library["thrash"][1]), thrash) > 0.9
    # Nearest to a thrash track: the other thrash tracks and the heavy ones before any pop.
    query = index.query_from([map_library["thrash"][0]])
    nearest = [tid for tid, _ in index.nearest(query, 8, exclude={map_library["thrash"][0]})]
    pop_rank = min(nearest.index(t) for t in map_library["pop"] if t in nearest) if any(t in nearest for t in map_library["pop"]) else 99
    heavy_rank = min(nearest.index(t) for t in map_library["heavy"] if t in nearest)
    assert heavy_rank < pop_rank
    # Steering away from the heavy act lowers the heavy tracks' fit.
    before = index.fit(map_library["heavy"], query)
    steered = index.steer(query, less_artist_keys=["map heavy"])
    after = index.fit(map_library["heavy"], steered)
    assert all(after[t] < before[t] for t in map_library["heavy"])
    # And toward it raises them.
    toward = index.steer(query, more_ids=map_library["heavy"][:1])
    assert all(index.fit(map_library["heavy"], toward)[t] > before[t] for t in map_library["heavy"])


def test_a_rebuild_replaces_the_map_and_the_cache_follows(db_session_factory, map_library):
    from app.models.track_vector import TrackVector
    from app.services.recommendations import vector_map

    db = db_session_factory()
    try:
        first = vector_map.rebuild_vector_map(db)
        second = vector_map.rebuild_vector_map(db)
        assert first["tracks_placed"] == second["tracks_placed"]
        assert db.query(TrackVector).filter(TrackVector.track_id.in_(map_library["all"])).count() == len(map_library["all"])
        index_a = vector_map.get_vector_index(db)
        vector_map.rebuild_vector_map(db)
        index_b = vector_map.get_vector_index(db)
        assert index_a is not index_b  # the rebuild dropped the cached copy
    finally:
        db.close()


def test_the_recommender_reads_the_map(db_session_factory, map_library):
    from app.services.recommendations import vector_map
    from app.services.recommendations.playlist_recommender import get_playlist_recommendations_from_track_ids

    db = db_session_factory()
    try:
        vector_map.rebuild_vector_map(db)
        answer = get_playlist_recommendations_from_track_ids(
            db, seed_track_ids=map_library["thrash"][:2], debug=True, limit=6, allow_genre_relaxation=True
        )
    finally:
        db.close()
    recs = answer["recommendations"]
    ids = [item["track"]["id"] for item in recs]
    assert ids, answer
    # Heavy before pop; pop may not appear at all.
    heavy_positions = [ids.index(t) for t in map_library["heavy"] if t in ids]
    pop_positions = [ids.index(t) for t in map_library["pop"] if t in ids]
    assert heavy_positions, ids
    assert not pop_positions or min(heavy_positions) < min(pop_positions)
    # The map spoke: every candidate carries its fit; the heavy act is nearer
    # than pop, and the track Last.fm tied to the seed is near enough to be
    # called aligned.
    fits = {item["track"]["id"]: item["debug"]["retrieval_sources"].get("vector") for item in recs}
    assert all(fit is not None for fit in fits.values()), fits
    heavy_fits = [fits[t] for t in map_library["heavy"] if t in fits]
    pop_fits = [fits[t] for t in map_library["pop"] if t in fits]
    assert min(heavy_fits) > (max(pop_fits) if pop_fits else 0.0), fits
    assert fits.get(map_library["heavy"][0], 0.0) >= 0.45, fits


def test_the_station_says_near_and_reaches_into_the_map_first():
    import app.services.radio as radio

    assert radio._neighbour_reason({"debug": {"retrieval_sources": {"vector": 0.7, "genre": 3}}}, "Map Thrash") == "Near Map Thrash"
    assert radio._neighbour_reason({"debug": {"retrieval_sources": {"vector": 0.2, "genre": 3}, "shared_families": ["rock_alt"]}}, "X") == "Shares rock with X"
    assert radio._neighbour_reason({"debug": {"retrieval_sources": {"vector": 0.9, "lastfm_track": 2}}}, "X") == "Similar to X"
    assert radio.REACH_NEAR == "near"


def test_no_map_is_no_map(db_session_factory, map_library):
    """Before the first build (or on a library with nothing to place) the
    channel is simply absent and nothing else changes."""
    from app.models.track_vector import ArtistVector, TrackVector
    from app.services.recommendations import vector_map
    from app.services.recommendations.retrievers.vector_retriever import retrieve_vector_candidates

    db = db_session_factory()
    try:
        db.query(TrackVector).delete(synchronize_session=False)
        db.query(ArtistVector).delete(synchronize_session=False)
        db.commit()
        vector_map.invalidate_vector_index()
        assert vector_map.get_vector_index(db) is None
        candidates, query, index = retrieve_vector_candidates(db, map_library["thrash"][:1], limit=5)
        assert candidates == {} and query is None and index is None
        vector_map.rebuild_vector_map(db)
        assert vector_map.get_vector_index(db) is not None
    finally:
        db.close()


def test_a_playlists_suggestions_put_new_artists_before_known_ones(db_session_factory, map_library):
    """Playlist suggestions only: a track by an artist already in the playlist
    keeps a quarter of the map's nearness bonus, so a near new artist comes
    first. For You and radio (the track-ids entry point) are unchanged."""
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack
    from app.services.recommendations import vector_map
    from app.services.recommendations.playlist_recommender import (
        get_playlist_recommendations_for_playlist,
        get_playlist_recommendations_from_track_ids,
    )
    from app.services.recommendations.scoring import score_candidate
    from app.models.track import Track

    db = db_session_factory()
    try:
        vector_map.rebuild_vector_map(db)
        playlist = Playlist(name="Map Thrash Only")
        db.add(playlist)
        db.flush()
        for position, track_id in enumerate(map_library["thrash"][:2]):
            db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=position))
        db.commit()
        known = map_library["thrash"][2]
        plain = get_playlist_recommendations_from_track_ids(db, seed_track_ids=map_library["thrash"][:2], debug=True, limit=6, allow_genre_relaxation=True)
        for_playlist = get_playlist_recommendations_for_playlist(db, playlist.id, debug=True, limit=6)
        plain_ids = [item["track"]["id"] for item in plain["recommendations"]]
        playlist_ids = [item["track"]["id"] for item in for_playlist["recommendations"]]
        # The known artist's last track scores lower through the playlist door
        # than through the track-ids door, and says why; the toy library is
        # too small for the order to turn on it (the real one is not — see
        # the probe numbers in the commit).
        assert known in plain_ids and known in playlist_ids, (plain_ids, playlist_ids)
        plain_known = next(item["debug"] for item in plain["recommendations"] if item["track"]["id"] == known)
        playlist_known = next(item["debug"] for item in for_playlist["recommendations"] if item["track"]["id"] == known)
        assert playlist_known["map_bonus"] < plain_known["map_bonus"] * 0.26
        assert any(reason.startswith("known_artist_map_share:x0.25") for reason in playlist_known["reasons"]), playlist_known["reasons"]
        assert not any(reason.startswith("known_artist_map_share") for reason in plain_known["reasons"])

        # And the rule is exactly a share of the bonus, nothing else.
        track = db.query(Track).filter(Track.id == known).one()
        full, full_debug = score_candidate(track, ["rock_alt"], {"rock_alt": 2}, {}, {"map thrash": 2}, {}, {"vector": 0.9}, map_strength=0.5)
        shared, shared_debug = score_candidate(track, ["rock_alt"], {"rock_alt": 2}, {}, {"map thrash": 2}, {}, {"vector": 0.9}, map_strength=0.5, known_artist_map_share=0.25)
        assert abs(shared_debug["map_bonus"] - full_debug["map_bonus"] * 0.25) < 1e-6
        assert abs((full - shared) - full_debug["map_bonus"] * 0.75) < 1e-6
        unknown, unknown_debug = score_candidate(track, ["rock_alt"], {"rock_alt": 2}, {}, {}, {}, {"vector": 0.9}, map_strength=0.5, known_artist_map_share=0.25)
        assert abs(unknown_debug["map_bonus"] - full_debug["map_bonus"]) < 1e-6
    finally:
        db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist.id).delete(synchronize_session=False)
        db.query(Playlist).filter(Playlist.id == playlist.id).delete(synchronize_session=False)
        db.commit()
        db.close()
