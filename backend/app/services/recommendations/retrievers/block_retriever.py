"""The map's extra blocks as retrieval channels: the tracks that sound like
the seeds ("sound") and the tracks whose words are about what the seeds'
words are about ("lyrics").

Each block answers on its own, from the seeds' mean position in that block,
so a track is proposed because it sounds right even when the tag map has it
far away — the ballad and the stadium single by one artist finally part
company here. Ranking weighs the channels low (ranking.CHANNEL_WEIGHTS);
they are tie-breakers beside the map, not reasons on their own.
"""

from __future__ import annotations

from app.services.recommendations.types import RetrievedCandidate
from app.services.recommendations.vector_map import VectorIndex

# One artist's share of a block's answer, as for the map.
NEAREST_PER_ARTIST = 4
# Block name → channel name the ranking knows.
CHANNEL_OF = {"sound": "sound", "words": "lyrics"}


def retrieve_block_candidates(
    index: VectorIndex | None,
    block: str,
    playlist_track_ids,
    limit: int,
    excluded_track_ids=None,
    block_query=None,
) -> dict[int, RetrievedCandidate]:
    if index is None or block not in index.blocks:
        return {}
    query = block_query if block_query is not None else index.block_query(block, playlist_track_ids)
    if query is None:
        return {}
    exclude = set(int(t) for t in (excluded_track_ids or ())) | set(int(t) for t in playlist_track_ids)
    channel = CHANNEL_OF.get(block, block)
    candidates: dict[int, RetrievedCandidate] = {}
    for track_id, cosine in index.block_nearest(block, query, limit, exclude=exclude, per_artist=NEAREST_PER_ARTIST):
        if cosine <= 0:
            break
        candidate = RetrievedCandidate(track_id=track_id)
        candidate.add_score(channel, cosine)
        candidates[track_id] = candidate
    return candidates
