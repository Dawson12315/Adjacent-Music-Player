from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.routes.tracks import build_track_responses_for_ids
from app.schemas.track import TrackResponse
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

    recommendations = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_track_ids,
        playlist_id=None,
        limit=limit,
    )

    return build_track_responses_for_ids(
        [recommendation.id for recommendation in recommendations],
        db,
    )
