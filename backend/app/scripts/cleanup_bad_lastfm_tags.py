from app.db import SessionLocal
from app.models.track import Track
from app.models.track_genre import TrackGenre


BAD_TAGS = {
    "Sweetener",
    "Peter",
    "Iggy Azalea",
    "God Is A Woman",
    "Love At First Listen",
    "Motomano",
    "Night",
    "Soty",
    "Aoty",
    "Eternal Sunshine",
    "Best Of 2018",
    "Best Of 2024",
    "Summer 2014",
    "Intro",
}


def main():
    db = SessionLocal()

    try:
        affected_track_ids = {
            row.track_id
            for row in db.query(TrackGenre).filter(TrackGenre.genre.in_(BAD_TAGS)).all()
        }

        deleted_count = db.query(TrackGenre).filter(
            TrackGenre.genre.in_(BAD_TAGS)
        ).delete(synchronize_session=False)

        if affected_track_ids:
            db.query(Track).filter(Track.id.in_(affected_track_ids)).update(
                {"lastfm_tags_enriched": False},
                synchronize_session=False,
            )

        db.commit()

        print(f"Deleted bad tags: {deleted_count}")
        print(f"Reset enrichment on tracks: {len(affected_track_ids)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()