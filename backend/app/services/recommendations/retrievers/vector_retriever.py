"""The map as a retrieval channel: the nearest tracks to the seeds' position.

Unlike the other channels this one can also say how far *any* candidate is
from the seeds, which `retrieval.annotate_vector_fit` uses to give every
merged candidate a `vector` score — so the ranking can tell a favourite
that happens to be near the seed from one that is nowhere near it.
"""

from __future__ import annotations

import numpy as np

from app.services.recommendations.types import RetrievedCandidate
from app.services.recommendations.vector_map import VectorIndex, get_vector_index

# One artist's share of the map's answer: enough for a station's cap, few
# enough that a prolific neighbour does not stand in for the neighbourhood.
NEAREST_PER_ARTIST = 4


def retrieve_vector_candidates(
    db,
    playlist_track_ids,
    limit: int,
    excluded_track_ids=None,
    query_vector: np.ndarray | None = None,
) -> tuple[dict[int, RetrievedCandidate], np.ndarray | None, VectorIndex | None]:
    index = get_vector_index(db)
    if index is None:
        return {}, None, None
    query = query_vector if query_vector is not None else index.query_from(playlist_track_ids)
    if query is None:
        return {}, None, index
    exclude = set(int(t) for t in (excluded_track_ids or ())) | set(int(t) for t in playlist_track_ids)
    candidates: dict[int, RetrievedCandidate] = {}
    for track_id, cosine in index.nearest(query, limit, exclude=exclude, per_artist=NEAREST_PER_ARTIST):
        if cosine <= 0:
            break
        candidate = RetrievedCandidate(track_id=track_id)
        candidate.add_score("vector", cosine)
        candidates[track_id] = candidate
    return candidates, query, index
