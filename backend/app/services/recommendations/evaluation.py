from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.models.listening_event import ListeningEvent
from app.models.playlist import Playlist
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)
from app.services.recommendations.retrievers.genre_retriever import (
    get_genre_family_map,
)


def persist_eval_run(db: Session, kind: str, params: dict, metrics: dict) -> None:
    """History row per run, so tuning changes can be compared over time."""
    db.execute(
        text(
            """
            INSERT INTO recommendation_eval_runs (kind, params_json, metrics_json)
            VALUES (:kind, :params_json, :metrics_json)
            """
        ),
        {
            "kind": kind,
            "params_json": json.dumps(params),
            "metrics_json": json.dumps(metrics),
        },
    )
    db.commit()


def list_eval_history(db: Session, limit: int = 50) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT id, kind, params_json, metrics_json, created_at
            FROM recommendation_eval_runs
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).fetchall()

    return [
        {
            "id": row[0],
            "kind": row[1],
            "params": json.loads(row[2]),
            "metrics": json.loads(row[3]),
            "created_at": row[4],
        }
        for row in rows
    ]


def evaluate_temporal_split(
    db: Session,
    user_id: int,
    top_k: int = 20,
    test_fraction: float = 0.2,
    seed_limit: int = 10,
    baseline_samples: int = 20,
) -> dict[str, Any]:
    """The honest test: train on the past, predict the future.

    Splits the user's play history at a point in time, seeds the recommender
    with what they played before it, and asks how many of the tracks they
    *discovered afterwards* (first play in the test window) it would have
    surfaced. Random and genre-matched-random baselines give the uplift
    context — beating random is table stakes, beating genre-random is the
    system earning its complexity.
    """
    events = (
        db.query(ListeningEvent.track_id)
        .filter(
            ListeningEvent.user_id == user_id,
            ListeningEvent.event_type == "play_started",
        )
        .order_by(ListeningEvent.created_at.asc())
        .all()
    )

    play_sequence = [row[0] for row in events]

    if len(play_sequence) < 20:
        return {
            "eligible": False,
            "reason": f"Need at least 20 plays for a temporal split, found {len(play_sequence)}",
        }

    split_index = int(len(play_sequence) * (1.0 - test_fraction))
    train_plays = play_sequence[:split_index]
    test_plays = play_sequence[split_index:]

    train_track_set = set(train_plays)

    # Discovery targets: tracks whose first play falls in the test window.
    targets = list(dict.fromkeys(
        track_id for track_id in test_plays if track_id not in train_track_set
    ))

    if not targets:
        return {
            "eligible": False,
            "reason": "No first-time plays in the test window — nothing to predict",
        }

    seed_track_ids = [
        track_id
        for track_id, _count in Counter(train_plays).most_common(seed_limit)
    ]

    recommendations = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_track_ids,
        playlist_id=None,
        limit=top_k,
        user_id=user_id,
    )
    recommended_ids = [track.id for track in recommendations[:top_k]]

    target_set = set(targets)
    hits = [track_id for track_id in recommended_ids if track_id in target_set]

    # ---- baselines ----
    rng = random.Random(f"temporal-eval:{user_id}:{len(play_sequence)}")

    candidate_pool = [
        row[0]
        for row in db.query(Track.id).all()
        if row[0] not in train_track_set
    ]

    def sampled_precision(pool: list[int]) -> float:
        if not pool:
            return 0.0
        precisions = []
        for _ in range(baseline_samples):
            sample = rng.sample(pool, min(top_k, len(pool)))
            sample_hits = sum(1 for track_id in sample if track_id in target_set)
            precisions.append(sample_hits / max(len(sample), 1))
        return mean(precisions)

    random_precision = sampled_precision(candidate_pool)

    # Genre-matched pool: tracks sharing a family with the seeds.
    seed_tracks = (
        db.query(Track)
        .options(selectinload(Track.track_genres))
        .filter(Track.id.in_(seed_track_ids))
        .all()
    )
    seed_families = {
        family
        for track in seed_tracks
        for family in get_track_families(track)
    }

    genre_family_map = get_genre_family_map(db)
    matching_genres = [
        genre
        for genre, family in genre_family_map.items()
        if family in seed_families
    ]

    genre_pool: list[int] = []
    if matching_genres:
        from app.models.track_genre import TrackGenre

        genre_pool = list(
            {
                row[0]
                for row in db.query(TrackGenre.track_id)
                .filter(TrackGenre.genre.in_(matching_genres))
                .all()
                if row[0] not in train_track_set
            }
        )

    genre_random_precision = sampled_precision(genre_pool)

    system_precision = len(hits) / max(len(recommended_ids), 1)

    metrics = {
        "eligible": True,
        "plays_total": len(play_sequence),
        "train_plays": len(train_plays),
        "test_plays": len(test_plays),
        "discovery_targets": len(targets),
        "seed_track_ids": seed_track_ids,
        "recommended": len(recommended_ids),
        "hits": len(hits),
        "hit_track_ids": hits,
        "precision_at_k": system_precision,
        "recall_at_k": len(hits) / len(targets),
        "baseline_random_precision": random_precision,
        "baseline_genre_random_precision": genre_random_precision,
        "uplift_vs_random": (
            system_precision / random_precision if random_precision else None
        ),
        "uplift_vs_genre_random": (
            system_precision / genre_random_precision
            if genre_random_precision
            else None
        ),
    }

    persist_eval_run(
        db,
        kind="temporal",
        params={
            "user_id": user_id,
            "top_k": top_k,
            "test_fraction": test_fraction,
            "seed_limit": seed_limit,
        },
        metrics={k: v for k, v in metrics.items() if k not in ("seed_track_ids", "hit_track_ids")},
    )

    return metrics


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