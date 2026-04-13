from app.db import SessionLocal
from app.models.track import Track


def main():
    db = SessionLocal()

    try:
        artists = (
            db.query(Track.artist)
            .filter(Track.artist.isnot(None))
            .distinct()
            .order_by(Track.artist.asc())
            .all()
        )

        for (artist,) in artists:
            print(artist)
    finally:
        db.close()


if __name__ == "__main__":
    main()