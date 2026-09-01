from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.expression import func

from app.db import get_db
from app.dependencies.auth import get_current_user
from app.models.track import Track
from app.models.user import User
from app.routes.tracks import build_track_response, build_track_responses_for_ids
from app.schemas.track import TrackResponse
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)

router = APIRouter()

SIMILAR_TRACKS_LIMIT = 10


@router.get(
    "/tracks/{track_id}/similar",
    response_model=list[TrackResponse],
    tags=["tracks"],
)
def get_similar_tracks(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        return []

    recommendations = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=[track_id],
        playlist_id=None,
        limit=SIMILAR_TRACKS_LIMIT,
    )

    recommended_track_ids = [recommendation.id for recommendation in recommendations]

    if recommended_track_ids:
        return build_track_responses_for_ids(recommended_track_ids, db)

    if not track.genre:
        return []

    similar_tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(
            Track.genre == track.genre,
            Track.id != track.id,
        )
        .order_by(func.random())
        .limit(SIMILAR_TRACKS_LIMIT)
        .all()
    )

    return [build_track_response(similar_track, db) for similar_track in similar_tracks]
