from collections import Counter
from itertools import combinations

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.playlist_track import PlaylistTrack
from app.models.track_cooccurrence import TrackCooccurrence


def rebuild_track_cooccurrence(db: Session) -> dict:
    playlist_rows = (
        db.query(PlaylistTrack)
        .order_by(PlaylistTrack.playlist_id.asc(), PlaylistTrack.position.asc())
        .all()
    )

    playlist_to_tracks: dict[int, list[int]] = {}

    for row in playlist_rows:
        playlist_to_tracks.setdefault(row.playlist_id, []).append(row.track_id)

    pair_counts: Counter[tuple[int, int]] = Counter()

    for track_ids in playlist_to_tracks.values():
        unique_track_ids = sorted(set(track_ids))

        if len(unique_track_ids) < 2:
            continue

        for track_a_id, track_b_id in combinations(unique_track_ids, 2):
            pair_counts[(track_a_id, track_b_id)] += 1

    db.query(TrackCooccurrence).delete()

    new_rows = [
        TrackCooccurrence(
            track_a_id=track_a_id,
            track_b_id=track_b_id,
            cooccurrence_count=count,
        )
        for (track_a_id, track_b_id), count in pair_counts.items()
    ]

    if new_rows:
        db.bulk_save_objects(new_rows)

    db.commit()

    return {
        "playlists_scanned": len(playlist_to_tracks),
        "pairs_written": len(new_rows),
    }


def main() -> None:
    db = SessionLocal()
    try:
        result = rebuild_track_cooccurrence(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()