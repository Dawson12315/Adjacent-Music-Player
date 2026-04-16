from app.db import SessionLocal
from app.models.track import Track
from app.models.track_genre import TrackGenre
from app.services.lastfm_enrichment import enrich_track_lastfm_tags


TRACK_ID = 263


def main():
    db = SessionLocal()

    try:
        db.query(TrackGenre).filter(
            TrackGenre.track_id == TRACK_ID,
            TrackGenre.genre != "Alternative",
        ).delete(synchronize_session=False)

        track = db.query(Track).filter(Track.id == TRACK_ID).first()
        track.lastfm_tags_enriched = False
        db.commit()

        before = db.query(TrackGenre).filter(TrackGenre.track_id == TRACK_ID).all()
        print("BEFORE:", [row.genre for row in before])

        result = enrich_track_lastfm_tags(db, TRACK_ID)
        print("RESULT:", result)

        after = db.query(TrackGenre).filter(TrackGenre.track_id == TRACK_ID).all()
        print("AFTER:", [row.genre for row in after])

    finally:
        db.close()


if __name__ == "__main__":
    main()