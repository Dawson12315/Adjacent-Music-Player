from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.lastfm import get_track_top_tags
from app.services.lastfm_genre_filter import clean_lastfm_genre_tags
from app.models.track_genre import TrackGenre
from app.utils.artist_parsing import extract_featured_artists


TRACK_ID = 263


def main():
    db = SessionLocal()

    try:
        track = db.query(Track).filter(Track.id == TRACK_ID).first()
        settings = db.query(AppSetting).first()

        if not track:
            print("Track not found")
            return

        if not settings or not settings.lastfm_api_key:
            print("Missing Last.fm API key")
            return

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
        artist_names.extend(extract_featured_artists(track.raw_album or ""))

        artist_names = [name.strip() for name in artist_names if name]

        result = get_track_top_tags(
            track.musicbrainz_recording_id,
            settings.lastfm_api_key,
            track_name=track.title,
            artist_name=track.artist,
        )

        existing_genres = [
            row.genre
            for row in db.query(TrackGenre).filter(TrackGenre.track_id == track.id).all()
        ]

        print("=== TRACK ===")
        print("id:", track.id)
        print("title:", track.title)
        print("artist:", track.artist)
        print("album:", track.album)
        print("mbid:", track.musicbrainz_recording_id)
        print("existing genres:", existing_genres)
        print("artist names used for filtering:", artist_names)
        print()

        print("=== LAST.FM RESULT ===")
        print(result)
        print()

        raw_tags = result.get("tags", [])
        cleaned_tags = clean_lastfm_genre_tags(
            raw_tags,
            artist_names=artist_names,
            track_title=track.title,
            album_title=track.album,
        )

        print("=== RAW TAGS ===")
        print(raw_tags)
        print()

        print("=== CLEANED TAGS ===")
        print(cleaned_tags)

    finally:
        db.close()


if __name__ == "__main__":
    main()