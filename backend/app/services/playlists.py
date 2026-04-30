from sqlalchemy.orm import Session

from app.models.playlist import Playlist


def liked_songs_system_key(user_id: int) -> str:
    return f"liked_songs:{user_id}"


def ensure_liked_songs_playlist(db: Session, user_id: int) -> Playlist:
    system_key = liked_songs_system_key(user_id)

    liked_songs = (
        db.query(Playlist)
        .filter(
            Playlist.user_id == user_id,
            Playlist.system_key == system_key,
        )
        .first()
    )

    if liked_songs:
        if liked_songs.name == "Liked Songs":
            liked_songs.name = "Loved Songs"
            db.commit()
            db.refresh(liked_songs)

        return liked_songs

    old_global_liked_songs = (
        db.query(Playlist)
        .filter(
            Playlist.user_id.is_(None),
            Playlist.system_key == "liked_songs",
        )
        .first()
    )

    if old_global_liked_songs:
        old_global_liked_songs.user_id = user_id
        old_global_liked_songs.system_key = system_key
        old_global_liked_songs.name = "Loved Songs"
        old_global_liked_songs.is_system = True

        db.commit()
        db.refresh(old_global_liked_songs)

        return old_global_liked_songs

    liked_songs = Playlist(
        user_id=user_id,
        name="Loved Songs",
        is_system=True,
        system_key=system_key,
    )

    db.add(liked_songs)
    db.commit()
    db.refresh(liked_songs)

    return liked_songs