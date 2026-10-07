"""A playlist that has found its genre may hear a neighbour.

Twenty songs, four in five of them one genre: the strict gates built to stop
a two-genre playlist drifting stand down for it, and a track the other
channels vouch for can land. Nineteen songs, or seventy-nine per cent, keep
the gates up; a one-track "similar" seed and the for-you list never qualify.
"""

from collections import Counter

import pytest

from app.models.track import Track
from app.models.track_genre import TrackGenre
from app.services.recommendations.playlist_recommender import (
    RELAX_GENRE_DOMINANT_SHARE,
    RELAX_GENRE_MIN_TRACKS,
    build_playlist_profile,
)
from app.services.recommendations.ranking import rank_candidates
from app.services.recommendations.reasoning import summarize_recommendation_reason
from app.services.recommendations.types import RetrievedCandidate
from tests.test_pass_p import _admin, _make_track


def _track(index: int, *genres: str) -> Track:
    track = Track(id=index, title=f"T{index}", artist="A", file_path=f"/t/{index}.flac")
    if len(genres) == 1:
        track.genre = genres[0]
    else:
        track.track_genres = [TrackGenre(genre=genre) for genre in genres]
    return track


def _playlist(jazz: int, other: int = 0, other_genre: str = "Rock") -> list[Track]:
    tracks = [_track(i, "Jazz") for i in range(jazz)]
    tracks += [_track(100 + i, other_genre) for i in range(other)]
    return tracks


# --- the profile ---------------------------------------------------------------


def test_twenty_songs_four_in_five_one_genre_relaxes():
    profile = build_playlist_profile(_playlist(16, 4), allow_genre_relaxation=True)

    assert profile["track_count"] == 20
    assert profile["dominant_track_share"] == pytest.approx(0.8)
    assert profile["genre_restriction_relaxed"] is True


def test_nineteen_songs_do_not():
    profile = build_playlist_profile(_playlist(19), allow_genre_relaxation=True)

    assert profile["dominant_track_share"] == 1.0
    assert profile["genre_restriction_relaxed"] is False


def test_seventy_nine_per_cent_does_not():
    profile = build_playlist_profile(_playlist(15, 5), allow_genre_relaxation=True)

    assert profile["dominant_track_share"] == pytest.approx(0.75)
    assert profile["genre_restriction_relaxed"] is False


def test_a_multi_genre_song_counts_once():
    # Sixteen songs tagged both Jazz and Rock: as family *mentions* that is
    # sixteen of each, a fifty-fifty split; as songs it is sixteen jazz.
    tracks = [_track(i, "Jazz", "Rock") for i in range(16)] + [_track(100 + i, "Soul") for i in range(4)]
    profile = build_playlist_profile(tracks, allow_genre_relaxation=True)

    assert profile["family_counts"]["jazz_blues"] == 16
    assert profile["family_counts"]["rock_alt"] == 16
    assert profile["tracks_per_family"] == Counter({"jazz_blues": 16, "rnb_soul": 4})
    assert profile["genre_restriction_relaxed"] is True


def test_only_a_playlist_earns_it():
    # The same twenty songs as a for-you or similar-tracks seed: never.
    profile = build_playlist_profile(_playlist(20))

    assert profile["genre_restriction_relaxed"] is False
    assert (RELAX_GENRE_MIN_TRACKS, RELAX_GENRE_DOMINANT_SHARE) == (20, 0.8)


# --- the ranking gate ----------------------------------------------------------


def _rank(relaxed: bool):
    rock = _track(500, "Rock")
    retrieved = {500: RetrievedCandidate(track_id=500, source_scores={"cooccurrence": 4.0})}
    profile = {
        "focused_playlist": True,
        "metadata_sparse": False,
        "is_multi_cluster": False,
        "genre_restriction_relaxed": relaxed,
    }
    scored, debug = rank_candidates(
        candidate_tracks=[rock],
        family_counts=Counter({"jazz_blues": 20}),
        cooccurrence_scores={500: 4.0},
        playlist_artist_counts=Counter(),
        playlist_album_counts=Counter(),
        retrieved_candidates=retrieved,
        playlist_profile=profile,
    )
    return scored, debug.get(500)


def test_a_focused_playlist_gates_an_off_genre_track():
    scored, debug = _rank(relaxed=False)

    # Gated out entirely: not ranked, and not even in the debug record.
    assert scored == []
    assert debug is None


def test_a_relaxed_playlist_lets_it_through_and_says_why():
    scored, debug = _rank(relaxed=True)

    assert [track.id for _score, track in scored] == [500]
    assert "relaxed_genre_dominant_playlist" in debug["reasons"]
    assert summarize_recommendation_reason(debug) == (
        "Something a little different, for a playlist that knows its sound"
    )


# --- end to end ------------------------------------------------------------------


def _tag(db_session_factory, track_ids, genre):
    db = db_session_factory()
    try:
        for track_id in track_ids:
            db.add(TrackGenre(track_id=track_id, genre=genre))
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def settled_playlists(client, db_session_factory):
    """Twenty-one jazz songs and one rock song that keeps company with them.

    Playlist "Settled" holds twenty jazz songs; "Finding" holds nineteen.
    The rock song co-occurs with the first nineteen, so both playlists
    retrieve it; only the settled one may keep it.
    """
    from app.models.playlist import Playlist
    from app.models.playlist_track import PlaylistTrack
    from app.models.track_cooccurrence import TrackCooccurrence
    from app.services.recommendations.rec_cache import invalidate_library_caches

    _admin(client)
    jazz = [
        _make_track(db_session_factory, f"/lib/relax-jazz-{i}.flac", title=f"Jazz {i:02d}", artist=f"Quartet {i % 7}", album=f"Session {i % 5}")
        for i in range(21)
    ]
    rock = _make_track(db_session_factory, "/lib/relax-rock.flac", title="Neighbour", artist="Amps", album="Loud")
    _tag(db_session_factory, jazz, "Jazz")
    _tag(db_session_factory, [rock], "Rock")

    db = db_session_factory()
    try:
        for track_id in jazz[:19]:
            db.add(TrackCooccurrence(track_a_id=track_id, track_b_id=rock, cooccurrence_count=6))
        db.commit()
    finally:
        db.close()

    invalidate_library_caches()
    settled = client.post("/api/playlists", json={"name": "Settled"}).json()["id"]
    finding = client.post("/api/playlists", json={"name": "Finding"}).json()["id"]
    for track_id in jazz[:20]:
        client.post(f"/api/playlists/{settled}/tracks", json={"track_id": track_id})
    for track_id in jazz[:19]:
        client.post(f"/api/playlists/{finding}/tracks", json={"track_id": track_id})

    yield {"settled": settled, "finding": finding, "rock": rock, "jazz": jazz}

    # The database is shared across the session; leave nothing behind.
    db = db_session_factory()
    try:
        ids = jazz + [rock]
        for playlist_id in (settled, finding):
            db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).delete()
            db.query(Playlist).filter(Playlist.id == playlist_id).delete()
        db.query(TrackCooccurrence).filter(TrackCooccurrence.track_b_id == rock).delete()
        db.query(TrackGenre).filter(TrackGenre.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    invalidate_library_caches()


def _recommendations(client, playlist_id):
    body = client.get(
        f"/api/playlists/{playlist_id}/recommendations", params={"limit": 20, "debug": "true"}
    ).json()
    ids = [item["track"]["id"] for item in body["recommendations"]]
    return ids, body["playlist_profile"]


def test_the_settled_playlist_is_offered_the_neighbour(client, settled_playlists):
    ids, profile = _recommendations(client, settled_playlists["settled"])

    assert profile["genre_restriction_relaxed"] is True
    assert profile["dominant_track_share"] == 1.0
    assert settled_playlists["rock"] in ids
    # And still its own kind: the spare jazz song is there too.
    assert settled_playlists["jazz"][20] in ids


def test_the_playlist_still_finding_itself_is_not(client, settled_playlists):
    ids, profile = _recommendations(client, settled_playlists["finding"])

    assert profile["genre_restriction_relaxed"] is False
    assert settled_playlists["rock"] not in ids
    assert settled_playlists["jazz"][20] in ids
