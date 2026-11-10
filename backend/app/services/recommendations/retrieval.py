import random

from app.services.recommendations.retrievers.block_retriever import (
    retrieve_block_candidates,
)
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
from app.services.recommendations.retrievers.vector_retriever import (
    retrieve_vector_candidates,
)
from app.services.recommendations.types import RetrievedCandidate

# How much a press of "refresh" may move a candidate's retrieval total, as a
# share of it. Four channels (co-occurrence, Last.fm track, behaviour, recent
# additions) return the same rows in the same order on every call, so without
# this a refresh only ever reshuffled the genre and Last.fm artist channels
# and the same candidates sat at the top of the pool. Zero when refresh is 0.
REFRESH_RETRIEVAL_JITTER = 0.15
# Candidates at least this near the seeds in the map keep a protected seat,
# nearest first; and when the pool is trimmed, a cosine counts for this
# many points beside the other channels' raw sums, or a track the map puts
# at 0.96 would lose its place to one three genre tags found.
VECTOR_PROTECT_COSINE = 0.45
VECTOR_PROTECTED_SEATS = 150
VECTOR_TRIM_WEIGHT = 5.0


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


def annotate_vector_fit(merged: dict, index, query, corrections=None) -> None:
    """Give every merged candidate the map's opinion of it, not only the
    ones the map proposed: the cosine to the seeds' position, clipped at
    zero. Ranking reads it to tell a favourite near the seed from one far
    away, and the radio reads it for its reason text."""
    if index is None or query is None:
        return
    wanted = [track_id for track_id, candidate in merged.items() if "vector" not in candidate.source_scores]
    for track_id, cosine in index.fit(wanted, query, corrections).items():
        merged[track_id].add_score("vector", max(0.0, cosine))


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
    vector_query=None,
):
    # This listener's standing corrections to the map (see radio_taste).
    from app.services.radio_taste import corrections_for
    from app.services.recommendations.vector_map import get_vector_index

    corrections = corrections_for(db, user_id, get_vector_index(db)) if user_id is not None else None

    vector_candidates, vector_query, vector_index = retrieve_vector_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        limit=min(max(limit, 200), 400),
        excluded_track_ids=excluded_track_ids,
        query_vector=vector_query,
        corrections=corrections,
    )

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

    # What the seeds sound like, and what their words are about: the map's
    # extra blocks, each a channel of its own (vector_map.BLOCK_KINDS).
    block_limit = min(max(limit // 2, 100), 200)
    sound_candidates = retrieve_block_candidates(vector_index, "sound", playlist_track_ids, block_limit, excluded_track_ids)
    words_candidates = retrieve_block_candidates(vector_index, "words", playlist_track_ids, block_limit, excluded_track_ids)

    merged = merge_retrieved_candidates(
        vector_candidates,
        genre_candidates,
        cooccurrence_candidates,
        behavior_candidates,
        lastfm_artist_candidates,
        lastfm_track_candidates,
        recent_candidates,
        sound_candidates,
        words_candidates,
        excluded_track_ids=excluded_track_ids,
    )
    annotate_vector_fit(merged, vector_index, vector_query, corrections)

    if refresh > 0:
        jitter_rng = random.Random(f"retrieve:{playlist_id}:{refresh}")
        jitter = {
            track_id: 1.0 + jitter_rng.random() * REFRESH_RETRIEVAL_JITTER
            for track_id in sorted(merged)
        }
    else:
        jitter = {}

    def trim_key(item):
        track_id, candidate = item
        nearness = candidate.source_scores.get("vector", 0.0) * VECTOR_TRIM_WEIGHT
        return (candidate.total_retrieval_score + nearness) * jitter.get(track_id, 1.0)

    sorted_candidates = sorted(merged.items(), key=trim_key, reverse=True)

    protected_lastfm_track = [
        item
        for item in sorted_candidates
        if "lastfm_track" in item[1].source_scores
    ][:100]

    # The map's own nearest hundred always reach the ranking; a retrieval
    # total dominated by the other channels must not push them out.
    protected_vector = sorted(
        (item for item in sorted_candidates if item[1].source_scores.get("vector", 0.0) >= VECTOR_PROTECT_COSINE),
        key=lambda item: item[1].source_scores["vector"],
        reverse=True,
    )[:VECTOR_PROTECTED_SEATS]

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
        + protected_vector
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