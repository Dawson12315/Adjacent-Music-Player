from difflib import SequenceMatcher

from app.db import SessionLocal
from app.models.track import Track


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main():
    db = SessionLocal()

    try:
        artists = [
            artist for (artist,) in (
                db.query(Track.artist)
                .filter(Track.artist.isnot(None))
                .distinct()
                .order_by(Track.artist.asc())
                .all()
            )
            if artist
        ]

        seen = set()

        for i, artist_a in enumerate(artists):
            for artist_b in artists[i + 1:]:
                pair = tuple(sorted((artist_a, artist_b)))
                if pair in seen:
                    continue

                score = similarity(artist_a, artist_b)

                if score >= 0.88:
                    print(f"{score:.2f}  |  {artist_a}  <->  {artist_b}")
                    seen.add(pair)
    finally:
        db.close()


if __name__ == "__main__":
    main()