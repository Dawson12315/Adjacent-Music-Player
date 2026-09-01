from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.services.recommendations.evaluation import (
    evaluate_all_playlists_leave_one_out,
    evaluate_playlist_leave_one_out,
    evaluate_temporal_split,
    list_eval_history,
)

router = APIRouter()


@router.get(
    "/recommendations/evaluate/temporal",
    tags=["recommendation-evaluation"],
)
def evaluate_temporal(
    top_k: int = Query(20, ge=1, le=100),
    test_fraction: float = Query(0.2, gt=0.0, lt=0.9),
    seed_limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Train-on-past / predict-the-future evaluation with baselines."""
    try:
        return evaluate_temporal_split(
            db=db,
            user_id=current_user.id,
            top_k=top_k,
            test_fraction=test_fraction,
            seed_limit=seed_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/recommendations/evaluate/history",
    tags=["recommendation-evaluation"],
)
def evaluation_history(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return {"runs": list_eval_history(db, limit=limit)}


@router.get(
    "/recommendations/evaluate/playlists",
    tags=["recommendation-evaluation"],
)
def evaluate_all_playlists(
    top_k: int = Query(10, ge=1, le=100),
    min_playlist_size: int = Query(3, ge=2, le=1000),
    max_playlists: int | None = Query(None, ge=1, le=10000),
    max_holdouts_per_playlist: int | None = Query(None, ge=1, le=1000),
    include_system_playlists: bool = Query(False),
    refresh: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return evaluate_all_playlists_leave_one_out(
            db=db,
            top_k=top_k,
            min_playlist_size=min_playlist_size,
            max_playlists=max_playlists,
            max_holdouts_per_playlist=max_holdouts_per_playlist,
            include_system_playlists=include_system_playlists,
            refresh=refresh,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/recommendations/evaluate/playlists/{playlist_id}",
    tags=["recommendation-evaluation"],
)
def evaluate_single_playlist(
    playlist_id: int,
    top_k: int = Query(10, ge=1, le=100),
    max_holdouts: int | None = Query(None, ge=1, le=1000),
    refresh: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return evaluate_playlist_leave_one_out(
            db=db,
            playlist_id=playlist_id,
            top_k=top_k,
            max_holdouts=max_holdouts,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))