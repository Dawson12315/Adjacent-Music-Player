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

        if "track_cooccurrence" not in existing_table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE track_cooccurrence (
                        id INTEGER PRIMARY KEY,
                        track_a_id INTEGER NOT NULL,
                        track_b_id INTEGER NOT NULL,
                        cooccurrence_count INTEGER NOT NULL DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(track_a_id) REFERENCES tracks(id) ON DELETE CASCADE,
                        FOREIGN KEY(track_b_id) REFERENCES tracks(id) ON DELETE CASCADE,
                        CONSTRAINT uq_track_cooccurrence_pair UNIQUE (track_a_id, track_b_id)
                    )
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_cooccurrence_track_a_id
                ON track_cooccurrence(track_a_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_cooccurrence_track_b_id
                ON track_cooccurrence(track_b_id)
                """
            )
        )

        if "musicbrainz_recording_id" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN musicbrainz_recording_id TEXT")
            )

        if "lastfm_tags_enriched" not in track_column_names:
            connection.execute(
                text("ALTER TABLE tracks ADD COLUMN lastfm_tags_enriched BOOLEAN NOT NULL DEFAULT 0")
            )

        job_lock_columns = connection.execute(
            text("PRAGMA table_info(job_locks)")
        ).fetchall()
        job_lock_column_names = {column[1] for column in job_lock_columns}

        if "started_at" not in job_lock_column_names:
            connection.execute(
                text("ALTER TABLE job_locks ADD COLUMN started_at DATETIME")
            )

        app_settings_columns = connection.execute(
            text("PRAGMA table_info(app_settings)")
        ).fetchall()
        app_settings_column_names = {column[1] for column in app_settings_columns}

        if "lastfm_api_key" not in app_settings_column_names:
            connection.execute(
                text("ALTER TABLE app_settings ADD COLUMN lastfm_api_key TEXT")
            )

        if "lastfm_api_secret" not in app_settings_column_names:
            connection.execute(
                text("ALTER TABLE app_settings ADD COLUMN lastfm_api_secret TEXT")
            )

        if "lastfm_username" not in app_settings_column_names:
            connection.execute(
                text("ALTER TABLE app_settings ADD COLUMN lastfm_username TEXT")
            )

        if "lastfm_session_key" not in app_settings_column_names:
            connection.execute(
                text("ALTER TABLE app_settings ADD COLUMN lastfm_session_key TEXT")
            )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS listening_events (
                    id INTEGER PRIMARY KEY,
                    track_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    source_type TEXT,
                    source_id INTEGER,
                    position_seconds REAL,
                    duration_seconds REAL,
                    session_id TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_listening_events_track_id
                ON listening_events(track_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_listening_events_event_type
                ON listening_events(event_type)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_listening_events_session_id
                ON listening_events(session_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS track_user_stats (
                    id INTEGER PRIMARY KEY,
                    track_id INTEGER NOT NULL UNIQUE,
                    play_count INTEGER NOT NULL DEFAULT 0,
                    skip_count INTEGER NOT NULL DEFAULT 0,
                    completion_count INTEGER NOT NULL DEFAULT 0,
                    like_count INTEGER NOT NULL DEFAULT 0,
                    avg_completion_ratio REAL NOT NULL DEFAULT 0,
                    replay_score REAL NOT NULL DEFAULT 0,
                    playlist_add_count INTEGER NOT NULL DEFAULT 0,
                    last_played_at DATETIME,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_user_stats_track_id
                ON track_user_stats(track_id)
                """
            )
        )

        if "artist_lastfm_similarity" not in existing_table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE artist_lastfm_similarity (
                        id INTEGER PRIMARY KEY,
                        source_artist_name TEXT NOT NULL,
                        source_artist_key TEXT NOT NULL,
                        similar_artist_name TEXT NOT NULL,
                        similar_artist_key TEXT NOT NULL,
                        match_score REAL,
                        source_mbid TEXT,
                        similar_mbid TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_artist_similarity_pair UNIQUE (source_artist_key, similar_artist_key)
                    )
                    """
                )
            )
        
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_artist_similarity_source_key
                ON artist_lastfm_similarity(source_artist_key)
                """
            )
        )
        
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_artist_similarity_similar_key
                ON artist_lastfm_similarity(similar_artist_key)
                """
            )
        )

        if "track_lastfm_similarity" not in existing_table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE track_lastfm_similarity (
                        id INTEGER PRIMARY KEY,
                        source_track_id INTEGER NOT NULL,
                        similar_track_id INTEGER,
                        source_track_name TEXT NOT NULL,
                        source_artist_name TEXT NOT NULL,
                        similar_track_name TEXT NOT NULL,
                        similar_artist_name TEXT NOT NULL,
                        source_track_key TEXT NOT NULL,
                        similar_track_key TEXT NOT NULL,
                        match_score REAL,
                        source_mbid TEXT,
                        similar_mbid TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(source_track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                        FOREIGN KEY(similar_track_id) REFERENCES tracks(id) ON DELETE SET NULL,
                        CONSTRAINT uq_track_similarity_pair UNIQUE (source_track_id, similar_track_key)
                    )
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_similarity_source_track_id
                ON track_lastfm_similarity(source_track_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_similarity_similar_track_id
                ON track_lastfm_similarity(similar_track_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_similarity_source_key
                ON track_lastfm_similarity(source_track_key)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_track_similarity_similar_key
                ON track_lastfm_similarity(similar_track_key)
                """
            )
        )