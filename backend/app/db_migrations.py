from sqlalchemy import text

from app.db import engine


def run_simple_migrations():
    with engine.begin() as connection:
        playlist_columns = connection.execute(
            text("PRAGMA table_info(playlists)")
        ).fetchall()
        playlist_column_names = {column[1] for column in playlist_columns}

        if "artwork_path" not in playlist_column_names:
            connection.execute(
                text("ALTER TABLE playlists ADD COLUMN artwork_path TEXT")
            )

        track_columns = connection.execute(
            text("PRAGMA table_info(tracks)")
        ).fetchall()
        track_column_names = {column[1] for column in track_columns}

        if "raw_title" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN raw_title TEXT")
            )

        if "raw_artist" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN raw_artist TEXT")
            )

        if "raw_album" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN raw_album TEXT")
            )
            
        if "genre" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN genre TEXT")
            )

        if "raw_genre" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN raw_genre TEXT")
            )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS track_artists (
                    id INTEGER PRIMARY KEY,
                    track_id INTEGER NOT NULL,
                    artist_name TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_track_artist_pair
                ON track_artists(track_id, artist_name)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_artists_track_id
                ON track_artists(track_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_artists_artist_name
                ON track_artists(artist_name)
                """
            )
        )

        existing_tables = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        existing_table_names = {table[0] for table in existing_tables}

        if "track_genres" not in existing_table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE track_genres (
                        id INTEGER PRIMARY KEY,
                        track_id INTEGER NOT NULL,
                        genre TEXT NOT NULL,
                        FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                        CONSTRAINT uq_track_genre_pair UNIQUE (track_id, genre)
                    )
                    """
                )
            )

        if "musicbrainz_recording_id" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN musicbrainz_recording_id TEXT")
            )

        job_lock_columns = connection.execute(
            text("PRAGMA table_info(job_locks)")
        ).fetchall()
        job_lock_column_names = {column[1] for column in job_lock_columns}
        
        if "started_at" not in job_lock_column_names:
            connection.execute(
                text("ALTER TABLE job_locks ADD COLUMN started_at DATETIME")
            )