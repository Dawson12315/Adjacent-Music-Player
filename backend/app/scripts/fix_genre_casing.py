from app.db import SessionLocal
from app.models.track_genre import TrackGenre
from app.services.genre_normalizer import normalize_genre


def fix_genre_casing():
    db = SessionLocal()

    try:
        rows = db.query(TrackGenre).all()

        updated = 0

        for row in rows:
            normalized = normalize_genre(row.genre)

            if row.genre != normalized:
                print(f"{row.genre} -> {normalized}")
                row.genre = normalized
                updated += 1

        db.commit()
        print(f"Updated {updated} rows.")

    finally:
        db.close()


if __name__ == "__main__":
    fix_genre_casing()