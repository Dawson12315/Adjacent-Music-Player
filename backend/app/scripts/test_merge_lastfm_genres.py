from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.services.lastfm import get_track_top_tags
from app.services.lastfm_genre_filter import clean_lastfm_genre_tags
from app.utils.artist_parsing import extract_featured_artists


TRACK_ID_TO_TEST = 1


def main():
    db = SessionLocal()

    try:
        settings = db.query(AppSetting).first()
        api_key = settings.lastfm_api_key if settings else None

        track = (
            db.query(Track)
            .filter(Track.id == TRACK_ID_TO_TEST)
            .first()
        )

        if not track:
            print(f"Track {TRACK_ID_TO_TEST} not found.")
            return

        existing_rows = (
            db.query(TrackGenre)
            .filter(TrackGenre.track_id == track.id)
            .all()
        )
        existing_genres = [row.genre for row in existing_rows]

        print("=== BEFORE ===")
        print(f"title: {track.title}")
        print(f"artist: {track.artist}")
        print(f"existing genres: {existing_genres}")
        print()

        raw_tags = get_track_top_tags(
            track.musicbrainz_recording_id,
            api_key,
            track_name=track.title,
            artist_name=track.artist,
        )

        artist_names = []

        if track.artist:
            artist_names.append(track.artist)
        
        if track.raw_artist:
            artist_names.append(track.raw_artist)
        
        artist_names.extend(
            row.artist_name
            for row in db.query(TrackArtist).filter(TrackArtist.track_id == track.id).all()
        )
        
        artist_names.extend(extract_featured_artists(track.raw_title or ""))
        
        artist_names = [name.strip() for name in artist_names if name]

        cleaned_tags = clean_lastfm_genre_tags(
            raw_tags,
            artist_names=artist_names,
        )

        print("=== LAST.FM ===")
        print(f"raw tags: {raw_tags}")
        print(f"cleaned tags: {cleaned_tags}")
        print()

        existing_keys = {genre.casefold() for genre in existing_genres if genre}
        added = []

        for genre_name in cleaned_tags:
            if genre_name.casefold() in existing_keys:
                continue

            db.add(
                TrackGenre(
                    track_id=track.id,
                    genre=genre_name,
                )
            )
            existing_keys.add(genre_name.casefold())
            added.append(genre_name)

        if added:
            db.commit()
        else:
            print("No new genres to add.")

        updated_rows = (
            db.query(TrackGenre)
            .filter(TrackGenre.track_id == track.id)
            .all()
        )
        updated_genres = [row.genre for row in updated_rows]

        print("=== AFTER ===")
        print(f"added genres: {added}")
        print(f"all genres: {updated_genres}")

    finally:
        db.close()


if __name__ == "__main__":
    main()