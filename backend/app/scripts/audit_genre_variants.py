from app.db import SessionLocal
from app.models.track import Track
from app.models.track_genre import TrackGenre


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(TrackGenre, Track)
            .join(Track, Track.id == TrackGenre.track_id)
            .order_by(TrackGenre.genre.asc(), Track.id.asc())
            .all()
        )

        current_genre = None
        for track_genre, track in rows:
            if track_genre.genre != current_genre:
                current_genre = track_genre.genre
                print(f"\nGENRE: {current_genre}")

            print(
                f"  track_id={track.id} | title={track.title} | "
                f"artist={track.artist} | raw_genre={track.raw_genre}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()