from app.db import SessionLocal
from app.models.track import Track

def main():
    db = SessionLocal()
    try:
        track = db.query(Track).filter(Track.id == 1).first()

        if not track:
            print("Track not found")
            return

        print("Before:")
        print(track.id, track.title, track.genre, track.raw_genre)

        track.raw_genre = "Pop, Dance"
        db.commit()
        db.refresh(track)

        print("After:")
        print(track.id, track.title, track.genre, track.raw_genre)
    finally:
        db.close()

if __name__ == "__main__":
    main()