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