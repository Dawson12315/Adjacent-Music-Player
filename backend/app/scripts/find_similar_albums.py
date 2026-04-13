from difflib import SequenceMatcher

from app.db import SessionLocal
from app.models.track import Track


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main():
    db = SessionLocal()

    try:
        albums = [
            album for (album,) in (
                db.query(Track.album)
                .filter(Track.album.isnot(None))
                .distinct()
                .order_by(Track.album.asc())
                .all()
            )
            if album
        ]

        seen = set()

        for i, album_a in enumerate(albums):
            for album_b in albums[i + 1:]:
                pair = tuple(sorted((album_a, album_b)))
                if pair in seen:
                    continue

                score = similarity(album_a, album_b)

                if score >= 0.88:
                    print(f"{score:.2f}  |  {album_a}  <->  {album_b}")
                    seen.add(pair)
    finally:
        db.close()


if __name__ == "__main__":
    main()