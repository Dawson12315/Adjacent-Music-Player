from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _get_playlist_track_ids(db: Session, playlist_id: int) -> list[int]:
    rows = (
        db.query(PlaylistTrack)
        .filter(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position.asc())
        .all()
    )
    return [row.track_id for row in rows]


def _evaluate_single_holdout(
    db: Session,
    playlist_id: int,
    seed_track_ids: list[int],
    held_out_track_id: int,
    top_k: int,
    refresh: int = 0,
) -> dict[str, Any]:
    recommendations = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_track_ids,
        debug=False,
        refresh=refresh,
        playlist_id=playlist_id,
    )

    recommended_track_ids = [track.id for track in recommendations[:top_k]]

    hit = held_out_track_id in recommended_track_ids
    rank = None

    if hit:
        rank = recommended_track_ids.index(held_out_track_id) + 1

    reciprocal_rank = 0.0 if rank is None else 1.0 / rank

    return {
        "held_out_track_id": held_out_track_id,
        "seed_track_ids": seed_track_ids,
        "recommended_track_ids": recommended_track_ids,
        "hit": hit,
        "rank": rank,
        "reciprocal_rank": reciprocal_rank,
    }


def evaluate_playlist_leave_one_out(
    db: Session,
    playlist_id: int,
    top_k: int = 10,
    max_holdouts: int | None = None,
    refresh: int = 0,
) -> dict[str, Any]:
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise ValueError(f"Playlist {playlist_id} not found")

    playlist_track_ids = _get_playlist_track_ids(db, playlist_id)

    if len(playlist_track_ids) < 2:
        return {
            "playlist_id": playlist.id,
            "playlist_name": playlist.name,
            "track_count": len(playlist_track_ids),
            "eligible": False,
            "reason": "Playlist must contain at least 2 tracks for leave-one-out evaluation",
            "holdouts_tested": 0,
            "hit_rate_at_k": 0.0,
            "mrr": 0.0,
            "avg_rank": None,
            "results": [],
        }

    holdout_track_ids = playlist_track_ids[:]
    if max_holdouts is not None:
        holdout_track_ids = holdout_track_ids[:max_holdouts]

    results: list[dict[str, Any]] = []

    for held_out_track_id in holdout_track_ids:
        seed_track_ids = [track_id for track_id in playlist_track_ids if track_id != held_out_track_id]

        if not seed_track_ids:
            continue

        result = _evaluate_single_holdout(
            db=db,
            playlist_id=playlist_id,
            seed_track_ids=seed_track_ids,
            held_out_track_id=held_out_track_id,
            top_k=top_k,
            refresh=refresh,
        )
        results.append(result)

    hits = sum(1 for result in results if result["hit"])
    reciprocal_ranks = [result["reciprocal_rank"] for result in results]
    ranks = [result["rank"] for result in results if result["rank"] is not None]

    return {
        "playlist_id": playlist.id,
        "playlist_name": playlist.name,
        "track_count": len(playlist_track_ids),
        "eligible": True,
        "holdouts_tested": len(results),
        "hit_rate_at_k": _safe_divide(hits, len(results)),
        "mrr": mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
        "avg_rank": mean(ranks) if ranks else None,
        "results": results,
    }


def evaluate_all_playlists_leave_one_out(
    db: Session,
    top_k: int = 10,
    min_playlist_size: int = 3,
    max_playlists: int | None = None,
    max_holdouts_per_playlist: int | None = None,
    include_system_playlists: bool = False,
    refresh: int = 0,
) -> dict[str, Any]:
    query = db.query(Playlist).order_by(Playlist.id.asc())

    if not include_system_playlists:
        query = query.filter(Playlist.is_system.is_(False))

    playlists = query.all()

    if max_playlists is not None:
        playlists = playlists[:max_playlists]

    playlist_results: list[dict[str, Any]] = []
    all_holdout_results: list[dict[str, Any]] = []

    hit_counts_by_playlist_size: dict[int, dict[str, int]] = defaultdict(
        lambda: {"hits": 0, "total": 0}
    )

    for playlist in playlists:
        playlist_track_ids = _get_playlist_track_ids(db, playlist.id)

        if len(playlist_track_ids) < min_playlist_size:
            playlist_results.append(
                {
                    "playlist_id": playlist.id,
                    "playlist_name": playlist.name,
                    "track_count": len(playlist_track_ids),
                    "eligible": False,
                    "reason": f"Playlist smaller than min_playlist_size={min_playlist_size}",
                    "holdouts_tested": 0,
                    "hit_rate_at_k": 0.0,
                    "mrr": 0.0,
                    "avg_rank": None,
                    "results": [],
                }
            )
            continue

        result = evaluate_playlist_leave_one_out(
            db=db,
            playlist_id=playlist.id,
            top_k=top_k,
            max_holdouts=max_holdouts_per_playlist,
            refresh=refresh,
        )

        playlist_results.append(result)

        if result["eligible"]:
            for holdout_result in result["results"]:
                all_holdout_results.append(
                    {
                        "playlist_id": playlist.id,
                        "playlist_name": playlist.name,
                        "track_count": len(playlist_track_ids),
                        **holdout_result,
                    }
                )

                size_bucket = len(playlist_track_ids)
                hit_counts_by_playlist_size[size_bucket]["total"] += 1
                if holdout_result["hit"]:
                    hit_counts_by_playlist_size[size_bucket]["hits"] += 1

    total_holdouts = len(all_holdout_results)
    total_hits = sum(1 for result in all_holdout_results if result["hit"])
    reciprocal_ranks = [result["reciprocal_rank"] for result in all_holdout_results]
    ranks = [result["rank"] for result in all_holdout_results if result["rank"] is not None]

    eligible_playlist_results = [result for result in playlist_results if result["eligible"]]
    playlist_hit_rates = [result["hit_rate_at_k"] for result in eligible_playlist_results]
    playlist_mrrs = [result["mrr"] for result in eligible_playlist_results]

    hit_rate_by_playlist_size = {
        playlist_size: _safe_divide(bucket["hits"], bucket["total"])
        for playlist_size, bucket in sorted(hit_counts_by_playlist_size.items())
    }

    return {
        "summary": {
            "top_k": top_k,
            "min_playlist_size": min_playlist_size,
            "playlists_considered": len(playlists),
            "eligible_playlists": len(eligible_playlist_results),
            "holdouts_tested": total_holdouts,
            "overall_hit_rate_at_k": _safe_divide(total_hits, total_holdouts),
            "overall_mrr": mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
            "overall_avg_rank": mean(ranks) if ranks else None,
            "avg_playlist_hit_rate_at_k": mean(playlist_hit_rates) if playlist_hit_rates else 0.0,
            "avg_playlist_mrr": mean(playlist_mrrs) if playlist_mrrs else 0.0,
            "hit_rate_by_playlist_size": hit_rate_by_playlist_size,
        },
        "playlists": playlist_results,
    }