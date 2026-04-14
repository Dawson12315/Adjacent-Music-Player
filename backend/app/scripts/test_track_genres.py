from app.db import SessionLocal
from app.models.track import Track
from app.models.track_genre import TrackGenre


def main():
    db = SessionLocal()

    try:
        genre_rows = db.query(TrackGenre).limit(10).all()
        print("\n=== TRACK_GENRES SAMPLE ===")
        print([(row.track_id, row.genre) for row in genre_rows])

        if not genre_rows:
            print("\nNo track_genres rows found.")
            return

        track_id = genre_rows[0].track_id

        track = db.query(Track).filter(Track.id == track_id).first()
        linked_genres = db.query(TrackGenre).filter(
            TrackGenre.track_id == track_id
        ).all()

        print("\n=== TRACK CHECK ===")
        print("Track:", track.title)
        print("Primary genre (Track.genre):", track.genre)
        print("Raw genre:", track.raw_genre)
        print("Linked genres:", [g.genre for g in linked_genres])

    finally:
        db.close()


if __name__ == "__main__":
    main()