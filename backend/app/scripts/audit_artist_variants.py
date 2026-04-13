from collections import defaultdict

from app.db import SessionLocal
from app.models.track import Track


def main():
    db = SessionLocal()

    try:
        groups = defaultdict(list)

        tracks = db.query(Track).all()

        for track in tracks:
            normalized_artist = (track.artist or "").strip()
            raw_artist = (track.raw_artist or "").strip()

            if not normalized_artist:
                continue

            groups[normalized_artist].append(raw_artist or "(empty raw artist)")

        for normalized_artist in sorted(groups.keys()):
            raw_values = sorted(set(groups[normalized_artist]))
            if len(raw_values) <= 1:
                continue

            print(f"\nNORMALIZED: {normalized_artist}")
            for raw_value in raw_values:
                print(f"  - RAW: {raw_value}")

    finally:
        db.close()


if __name__ == "__main__":
    main()