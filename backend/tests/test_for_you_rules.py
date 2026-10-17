"""The home rail's two rules: shown songs sit out for three days, and a
liked song is never the answer. Both are additive on the For you path; the
playlist recommender's defaults are pinned here too."""

from datetime import datetime, timedelta

import pytest

from app.services.recommendations.dismissals import (
    DISMISSAL_DAYS,
    FOR_YOU_DISMISSAL_DAYS,
    FOR_YOU_SCOPE,
    dismiss_tracks,
    dismissed_track_ids,
)
from tests.test_pass_p import _admin, _make_track
from tests.test_track_numbers_and_dismissals import _credit


def _stats(db_session_factory, user_id, track_ids, **fields):
    from app.models.track_user_stats import TrackUserStats

    db = db_session_factory()
    try:
        for track_id in track_ids:
            row = db.query(TrackUserStats).filter_by(user_id=user_id, track_id=track_id).first()
            if row is None:
                row = TrackUserStats(user_id=user_id, track_id=track_id)
                db.add(row)
            for key, value in fields.items():
                setattr(row, key, value)
        db.commit()
    finally:
        db.close()


def _user_id(db_session_factory):
    from app.models.user import User

    db = db_session_factory()
    try:
        return db.query(User).filter_by(username="admin").one().id
    finally:
        db.close()


@pytest.fixture(scope="module")
def taste_library(client, db_session_factory):
    """Sixty tracks in one genre: ten played (the seeds), fifteen liked, the
    rest open. The genre retriever has plenty to offer after the exclusions."""
    _admin(client)
    user_id = _user_id(db_session_factory)
    ids = [
        _make_track(db_session_factory, f"/lib/fy-{i}.flac", title=f"ForYou {i:02d}", artist=f"FY Artist {i % 6}", album=f"FY Album {i % 4}")
        for i in range(60)
    ]
    _credit(db_session_factory, ids, "ForYou Act", genre="ForYouGenre")
    from app.services.recommendations.rec_cache import invalidate_library_caches

    invalidate_library_caches()

    seeds, liked, open_ids = ids[:10], ids[10:25], ids[25:]
    _stats(db_session_factory, user_id, seeds, play_count=5, completion_count=4, last_played_at=datetime.utcnow())
    for track_id in liked:
        response = client.post("/api/playlists/liked-songs/tracks", json={"track_id": track_id})
        assert response.status_code in (200, 201), response.text
    # Liked tracks also carry glowing stats, which is what used to put them
    # at the top of the behaviour channel.
    _stats(db_session_factory, user_id, liked, play_count=3, like_count=1, completion_count=3)
    yield {"user_id": user_id, "seeds": seeds, "liked": liked, "open": open_ids}

    # Leave the shared database as it was found: the maintenance tests count
    # the whole library, and the recycle test counts every expired hold.
    from app.models.playlist_track import PlaylistTrack
    from app.models.recommendation_dismissal import RecommendationDismissal
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre
    from app.models.track_user_stats import TrackUserStats

    db = db_session_factory()
    try:
        for model in (PlaylistTrack, TrackUserStats, TrackArtist, TrackGenre):
            db.query(model).filter(model.track_id.in_(ids)).delete(synchronize_session=False)
        db.query(RecommendationDismissal).filter(
            RecommendationDismissal.user_id == user_id,
            RecommendationDismissal.playlist_id == FOR_YOU_SCOPE,
        ).delete(synchronize_session=False)
        db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    invalidate_library_caches()


def _for_you(client, refresh=0, limit=12):
    response = client.get("/api/recommendations/for-you", params={"limit": limit, "refresh": refresh})
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def test_liked_songs_are_never_recommended(client, taste_library):
    liked = set(taste_library["liked"])
    seen = []
    for refresh in (0, 1, 2):
        answer = _for_you(client, refresh=refresh)
        assert answer, "the fixture library must produce suggestions"
        assert not set(answer) & liked, f"refresh={refresh} suggested a liked song"
        assert not set(answer) & set(taste_library["seeds"])
        seen.append(answer)
    # Three serves, no repeats across them: the hold is working too.
    assert not set(seen[0]) & set(seen[1])
    assert not set(seen[1]) & set(seen[2])


def test_shown_songs_sit_out_for_three_days(client, db_session_factory, taste_library):
    user_id = taste_library["user_id"]
    db = db_session_factory()
    try:
        held = set(dismissed_track_ids(db, user_id, FOR_YOU_SCOPE))
        assert held, "every served rail is recorded"
        assert held <= set(taste_library["open"])

        # The hold is the rail's, not any playlist's.
        assert dismissed_track_ids(db, user_id, 1) == []

        # Three days and a second later, the hold has lapsed.
        later = datetime.utcnow() + timedelta(days=FOR_YOU_DISMISSAL_DAYS, seconds=1)
        assert dismissed_track_ids(db, user_id, FOR_YOU_SCOPE, now=later) == []
        # ...and before that it has not.
        sooner = datetime.utcnow() + timedelta(days=FOR_YOU_DISMISSAL_DAYS, seconds=-60)
        assert set(dismissed_track_ids(db, user_id, FOR_YOU_SCOPE, now=sooner)) == held

        # A playlist's hold keeps its own, longer, window.
        assert FOR_YOU_DISMISSAL_DAYS < DISMISSAL_DAYS
        dismiss_tracks(db, user_id, 1, list(held)[:1])
        assert dismissed_track_ids(db, user_id, 1, now=later) == list(held)[:1]
    finally:
        db.close()


def test_the_pool_refills_when_the_hold_is_large(client, db_session_factory, taste_library):
    # Hold everything open; the rail is empty rather than falling back to
    # liked songs or seeds.
    user_id = taste_library["user_id"]
    db = db_session_factory()
    try:
        dismiss_tracks(db, user_id, FOR_YOU_SCOPE, taste_library["open"], days=FOR_YOU_DISMISSAL_DAYS)
    finally:
        db.close()
    answer = _for_you(client, refresh=3)
    assert not set(answer) & set(taste_library["liked"])
    assert not set(answer) & set(taste_library["seeds"])


def test_the_playlist_recommender_defaults_are_untouched(client, db_session_factory, taste_library):
    from app.services.recommendations.playlist_recommender import (
        get_playlist_recommendations_from_track_ids,
    )

    db = db_session_factory()
    try:
        kwargs = dict(db=db, seed_track_ids=taste_library["seeds"], limit=12, user_id=taste_library["user_id"])
        plain = [t.id for t in get_playlist_recommendations_from_track_ids(**kwargs)]
        explicit = [t.id for t in get_playlist_recommendations_from_track_ids(**kwargs, exclude_track_ids=[], exclude_from_retrieval=False, exclude_liked_behavior=False)]
        assert plain == explicit
        # Without the rail's flags, liked songs are still fair game for a
        # playlist, exactly as before.
        assert set(plain) & set(taste_library["liked"])
    finally:
        db.close()
