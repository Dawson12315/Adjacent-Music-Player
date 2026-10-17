import random

from app.services.recommendations.retrievers.behavior_retriever import (
    retrieve_behavior_candidates,
)
from app.services.recommendations.retrievers.cooccurrence_retriever import (
    retrieve_cooccurrence_candidates,
)
from app.services.recommendations.retrievers.genre_retriever import (
    retrieve_genre_candidates,
)
from app.services.recommendations.retrievers.lastfm_artist_retriever import (
    retrieve_lastfm_artist_candidates,
)
from app.services.recommendations.retrievers.lastfm_track_retriever import (
    retrieve_lastfm_track_candidates,
)
from app.services.recommendations.retrievers.recent_additions_retriever import (
    retrieve_recent_addition_candidates,
)
from app.services.recommendations.types import RetrievedCandidate

# How much a press of "refresh" may move a candidate's retrieval total, as a
# share of it. Four channels (co-occurrence, Last.fm track, behaviour, recent
# additions) return the same rows in the same order on every call, so without
# this a refresh only ever reshuffled the genre and Last.fm artist channels
# and the same candidates sat at the top of the pool. Zero when refresh is 0.
REFRESH_RETRIEVAL_JITTER = 0.15


def merge_retrieved_candidates(*candidate_maps, excluded_track_ids=None):
    merged: dict[int, RetrievedCandidate] = {}

    for candidate_map in candidate_maps:
        for track_id, candidate in candidate_map.items():
            if track_id not in merged:
                merged[track_id] = RetrievedCandidate(track_id=track_id)

            for source_name, score in candidate.source_scores.items():
                merged[track_id].add_score(source_name, score)

    # The channels that take the seeds as a lookup key (co-occurrence, Last.fm
    # track similarity) cannot be handed an exclusion list without it being
    # read as more seeds; their answers are filtered here instead.
    if excluded_track_ids:
        for track_id in set(excluded_track_ids):
            merged.pop(track_id, None)

    return merged


def retrieve_candidates(
    db,
    playlist_track_ids,
    playlist_profile,
    limit: int = 400,
    refresh: int = 0,
    playlist_id: int | None = None,
    user_id: int | None = None,
    include_recent_additions: bool = False,
    excluded_track_ids: list[int] | None = None,
    exclude_liked_behavior: bool = False,
):
    genre_candidates = retrieve_genre_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        playlist_profile=playlist_profile,
        limit=limit,
        refresh=refresh,
        playlist_id=playlist_id,
        excluded_track_ids=excluded_track_ids,
    )

    cooccurrence_candidates = retrieve_cooccurrence_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        limit=limit,
    )

    behavior_candidates = retrieve_behavior_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        playlist_profile=playlist_profile,
        limit=max(limit, 150),
        user_id=user_id,
        excluded_track_ids=excluded_track_ids,
        exclude_liked=exclude_liked_behavior,
    )

    lastfm_artist_candidates = retrieve_lastfm_artist_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        playlist_profile=playlist_profile,
        limit=min(max(limit, 200), 300),
        refresh=refresh,
        playlist_id=playlist_id,
        user_id=user_id,
        excluded_track_ids=excluded_track_ids,
    )

    lastfm_track_candidates = retrieve_lastfm_track_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        limit=min(max(limit, 200), 300),
    )

    recent_candidates = {}
    if include_recent_additions:
        recent_candidates = retrieve_recent_addition_candidates(
            db=db,
            playlist_track_ids=playlist_track_ids,
            playlist_profile=playlist_profile,
            excluded_track_ids=excluded_track_ids,
        )

    merged = merge_retrieved_candidates(
        genre_candidates,
        cooccurrence_candidates,
        behavior_candidates,
        lastfm_artist_candidates,
        lastfm_track_candidates,
        recent_candidates,
        excluded_track_ids=excluded_track_ids,
    )

    if refresh > 0:
        jitter_rng = random.Random(f"retrieve:{playlist_id}:{refresh}")
        jitter = {
            track_id: 1.0 + jitter_rng.random() * REFRESH_RETRIEVAL_JITTER
            for track_id in sorted(merged)
        }
    else:
        jitter = {}

    sorted_candidates = sorted(
        merged.items(),
        key=lambda item: item[1].total_retrieval_score * jitter.get(item[0], 1.0),
        reverse=True,
    )

    protected_lastfm_track = [
        item
        for item in sorted_candidates
        if "lastfm_track" in item[1].source_scores
    ][:100]

    protected_lastfm = [
        item
        for item in sorted_candidates
        if "lastfm_artist" in item[1].source_scores
    ][:100]

    protected_behavior = [
        item
        for item in sorted_candidates
        if "behavior" in item[1].source_scores
    ][:100]

    final_items = []
    seen_track_ids = set()

    for track_id, candidate in (
        protected_lastfm_track
        + protected_lastfm
        + protected_behavior
        + sorted_candidates
    ):
        if track_id in seen_track_ids:
            continue

        final_items.append((track_id, candidate))
        seen_track_ids.add(track_id)

        if len(final_items) >= limit:
            break

    return dict(final_items)