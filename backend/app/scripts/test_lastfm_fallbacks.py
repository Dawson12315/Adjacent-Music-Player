from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.services.lastfm import (
    get_album_top_tags,
    get_artist_top_tags,
    get_track_top_tags,
)


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

        print("=== TRACK ===")
        print("title:", track.title)
        print("artist:", track.artist)
        print("album:", track.album)
        print("mbid:", track.musicbrainz_recording_id)
        print()

        track_result = get_track_top_tags(
            track.musicbrainz_recording_id,
            settings.lastfm_api_key,
            track_name=track.title,
            artist_name=track.artist,
        )

        album_result = get_album_top_tags(
            track.album,
            track.artist,
            settings.lastfm_api_key,
        )

        artist_result = get_artist_top_tags(
            track.artist,
            settings.lastfm_api_key,
        )

        print("=== TRACK TAGS ===")
        print(track_result)
        print()

        print("=== ALBUM TAGS ===")
        print(album_result)
        print()

        print("=== ARTIST TAGS ===")
        print(artist_result)

    finally:
        db.close()


if __name__ == "__main__":
    main()