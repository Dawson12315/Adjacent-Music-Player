from sqlalchemy.orm import Session

from app.models.playlist import Playlist


def ensure_liked_songs_playlist(db: Session) -> Playlist:
    liked_songs = (
        db.query(Playlist)
        .filter(Playlist.system_key == "liked_songs")
        .first()
    )

    if liked_songs:
        # Rename existing playlist if still using old name
        if liked_songs.name == "Liked Songs":
            liked_songs.name = "Loved Songs"
            db.commit()
            db.refresh(liked_songs)

        return liked_songs

    # New installs
    liked_songs = Playlist(
        name="Loved Songs",
        is_system=True,
        system_key="liked_songs",
    )

    db.add(liked_songs)
    db.commit()
    db.refresh(liked_songs)

    return liked_songs