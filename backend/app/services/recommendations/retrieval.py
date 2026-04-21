from app.services.recommendations.types import RetrievedCandidate
from app.services.recommendations.retrievers.genre_retriever import (
    retrieve_genre_candidates,
)
from app.services.recommendations.retrievers.cooccurrence_retriever import (
    retrieve_cooccurrence_candidates,
)
from app.services.recommendations.retrievers.behavior_retriever import (
    retrieve_behavior_candidates,
)


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
    family_counts,
    limit: int = 400,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    genre_candidates = retrieve_genre_candidates(
        db=db,
        playlist_track_ids=playlist_track_ids,
        family_counts=family_counts,
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
        limit=limit,
    )

    merged = merge_retrieved_candidates(
        genre_candidates,
        cooccurrence_candidates,
        behavior_candidates,
    )

    sorted_candidates = sorted(
        merged.items(),
        key=lambda item: item[1].total_retrieval_score,
        reverse=True,
    )

    return dict(sorted_candidates[:limit])