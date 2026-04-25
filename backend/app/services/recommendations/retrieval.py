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
from app.services.recommendations.types import RetrievedCandidate


def merge_retrieved_candidates(*candidate_maps):
    merged: dict[int, RetrievedCandidate] = {}

    for candidate_map in candidate_maps:
        for track_id, candidate in candidate_map.items():
            if track_id not in merged:
                merged[track_id] = RetrievedCandidate(track_id=track_id)

            for source_name, score in candidate.source_scores.items():
                merged[track_id].add_score(source_name, score)

    return merged


def retrieve_candidates(
    db,
    playlist_track_ids,
    playlist_profile,
    limit: int = 400,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    genre_candidates = retrieve_genre_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        playlist_profile=playlist_profile,
        limit=limit,
        refresh=refresh,
        playlist_id=playlist_id,
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
    )

    lastfm_artist_candidates = retrieve_lastfm_artist_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        playlist_profile=playlist_profile,
        limit=min(max(limit, 200), 300),
        refresh=refresh,
        playlist_id=playlist_id,
    )

    lastfm_track_candidates = retrieve_lastfm_track_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        limit=min(max(limit, 200), 300),
    )

    merged = merge_retrieved_candidates(
        genre_candidates,
        cooccurrence_candidates,
        behavior_candidates,
        lastfm_artist_candidates,
        lastfm_track_candidates,
    )

    sorted_candidates = sorted(
        merged.items(),
        key=lambda item: item[1].total_retrieval_score,
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