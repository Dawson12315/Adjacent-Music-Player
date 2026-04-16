from app.db import SessionLocal
from app.models.track_genre import TrackGenre
from app.services.lastfm_enrichment import enrich_track_lastfm_tags


TRACK_ID_TO_TEST = 1


def main():
    db = SessionLocal()

    try:
        before = db.query(TrackGenre).filter(TrackGenre.track_id == TRACK_ID_TO_TEST).all()
        print("BEFORE:", [row.genre for row in before])

        result = enrich_track_lastfm_tags(db, TRACK_ID_TO_TEST)
        print("RESULT:", result)

        after = db.query(TrackGenre).filter(TrackGenre.track_id == TRACK_ID_TO_TEST).all()
        print("AFTER:", [row.genre for row in after])

    finally:
        db.close()


if __name__ == "__main__":
    main()