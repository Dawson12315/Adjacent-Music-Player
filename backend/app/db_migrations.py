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