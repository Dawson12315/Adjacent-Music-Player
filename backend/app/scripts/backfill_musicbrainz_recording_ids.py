from app.services.musicbrainz_backfill import backfill_musicbrainz_recording_ids


def main():
    backfill_musicbrainz_recording_ids()


if __name__ == "__main__":
    main()