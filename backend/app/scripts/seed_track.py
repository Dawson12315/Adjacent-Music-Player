from app.db import SessionLocal
from app.models.track import Track


def main():
    db = SessionLocal()

    try:
        existing = db.query(Track).filter(
            Track.file_path == "/Volumes/media/music/sample/sample-track.mp3"
        ).first()

        if existing:
            print("Sample track already exists.")
            return

        track = Track(
            title="Sample Track",
            artist="Sample Artist",
            album="Sample Album",
            file_path="/Volumes/media/music/sample/sample-track.mp3",
        )

        db.add(track)
        db.commit()
        db.refresh(track)

        print(f"Inserted track with id={track.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()