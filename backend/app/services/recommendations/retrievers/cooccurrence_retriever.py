from collections import Counter, defaultdict
import math
import random

from sqlalchemy import case, func, literal
from sqlalchemy.orm import Session

from app.models.track_cooccurrence import TrackCooccurrence
from app.services.recommendations.types import RetrievedCandidate

# A playlist of thousands is represented by a sample of its tracks: the
# co-occurrence signal saturates long before that, and the IN list, the row
# set and the arithmetic all scaled with it. Two thousand seeds took a minute.
MAX_SEED_TRACKS = 200


def retrieve_cooccurrence_candidates(
    db: Session,
    playlist_track_ids: list[int],
    limit: int = 300,
):
    candidates: dict[int, RetrievedCandidate] = {}

    if not playlist_track_ids:
        return candidates

    seed_ids = list(dict.fromkeys(playlist_track_ids))

    if len(seed_ids) > MAX_SEED_TRACKS:
        seed_ids = random.Random(len(seed_ids)).sample(seed_ids, MAX_SEED_TRACKS)

    seed_set = set(seed_ids)

    # Aggregated in SQL: for each partner of a seed, the summed count and how
    # many distinct seeds it touches. The old code loaded every row touching
    # the playlist and tested membership against a *list*, four times per row.
    partner = case(
        (TrackCooccurrence.track_a_id.in_(seed_ids), TrackCooccurrence.track_b_id),
        else_=TrackCooccurrence.track_a_id,
    ).label("partner")
    seed = case(
        (TrackCooccurrence.track_a_id.in_(seed_ids), TrackCooccurrence.track_a_id),
        else_=TrackCooccurrence.track_b_id,
    ).label("seed")

    rows = (
        db.query(
            partner,
            func.sum(TrackCooccurrence.cooccurrence_count).label("total"),
            func.count(func.distinct(seed)).label("seeds"),
        )
        .filter(
            (TrackCooccurrence.track_a_id.in_(seed_ids))
            | (TrackCooccurrence.track_b_id.in_(seed_ids))
        )
        .group_by(partner)
        .order_by(func.sum(TrackCooccurrence.cooccurrence_count).desc())
        .limit(limit * 4)
        .all()
    )

    ranked_scores: list[tuple[int, float]] = []

    for partner_id, total_count, distinct_seed_count in rows:
        if partner_id in seed_set:
            continue
        normalized_score = (0.7 * math.log1p(float(total_count or 0))) + (
            1.5 * int(distinct_seed_count or 0)
        )
        ranked_scores.append((partner_id, normalized_score))

    ranked_scores.sort(key=lambda item: item[1], reverse=True)

    for track_id, score in ranked_scores[:limit]:
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id),
        )
        candidate.add_score("cooccurrence", float(score))

    return candidates
