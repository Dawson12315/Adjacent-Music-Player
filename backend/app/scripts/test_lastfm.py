from app.db import SessionLocal
from app.models.track import Track
from app.models.app_setting import AppSetting
from app.services.lastfm import get_track_top_tags


def main():
    db = SessionLocal()

    try:
        settings = db.query(AppSetting).first()
        api_key = settings.lastfm_api_key

        track = (
            db.query(Track)
            .filter(Track.musicbrainz_recording_id.isnot(None))
            .first()
        )

        print("=== TRACK ===")
        print("title:", track.title)
        print("artist:", track.artist)
        print("mbid:", track.musicbrainz_recording_id)

        print("\n=== LAST.FM TAGS ===")

        tags = get_track_top_tags(
            track.musicbrainz_recording_id,
            api_key,
            track_name=track.title,
            artist_name=track.artist,
        )

        print(tags)

    finally:
        db.close()


if __name__ == "__main__":
    main()