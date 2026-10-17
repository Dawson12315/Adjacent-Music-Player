from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.routes.tracks import build_track_responses_for_ids
from app.schemas.track import TrackResponse
from app.services.playlists import liked_track_ids
from app.services.recommendations.dismissals import (
    FOR_YOU_DISMISSAL_DAYS,
    FOR_YOU_SCOPE,
    dismiss_tracks,
    dismissed_track_ids,
)
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)
from app.services.stats_service import (
    get_recently_played_tracks,
    get_top_played_tracks,
)

router = APIRouter()

FOR_YOU_SEED_LIMIT = 10


@router.get(
    "/recommendations/for-you",
    response_model=list[TrackResponse],
    tags=["home"],
)
def get_for_you_recommendations(
    limit: int = Query(20, ge=1, le=100),
    refresh: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seed_tracks = get_top_played_tracks(db, current_user.id, limit=FOR_YOU_SEED_LIMIT)

    if not seed_tracks:
        seed_tracks = get_recently_played_tracks(
            db,
            current_user.id,
            limit=FOR_YOU_SEED_LIMIT,
        )

    seed_track_ids = [track.id for track in seed_tracks]

    if not seed_track_ids:
        return []

    # Not these: what the rail showed in the last three days, and anything the
    # listener already keeps. Liked tracks still shape the taste profile and
    # the seeds; they are just never the answer. Both lists go into the
    # retrievers rather than onto the ranked result, or a long liked list
    # would empty the pool.
    held = dismissed_track_ids(db, current_user.id, FOR_YOU_SCOPE)
    liked = liked_track_ids(db, current_user.id)

    recommendations = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_track_ids,
        playlist_id=None,
        limit=limit,
        refresh=refresh,
        user_id=current_user.id,
        include_recent_additions=True,
        exclude_track_ids=[*held, *liked],
        exclude_from_retrieval=True,
        exclude_liked_behavior=True,
    )

    # Shown is shown: these sit out for three days, on every surface that
    # asks, so a refresh moves on instead of dealing the same hand.
    dismiss_tracks(
        db,
        current_user.id,
        FOR_YOU_SCOPE,
        [recommendation.id for recommendation in recommendations],
        days=FOR_YOU_DISMISSAL_DAYS,
    )

    return build_track_responses_for_ids(
        [recommendation.id for recommendation in recommendations],
        db,
    )
