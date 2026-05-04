from pathlib import Path
from datetime import datetime, timedelta, timezone
import mimetypes
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from jose import JWTError, jwt

from app.config import settings
from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.album_artwork import AlbumArtwork
from app.models.app_setting import AppSetting
from app.models.artist_artwork import ArtistArtwork
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.models.user import User
from app.routes.albums import normalize_album_name
from app.schemas.track import TrackResponse
from app.schemas.track_edit import TrackUpdate
from app.services.lastfm import scrobble_track, update_now_playing
from app.services.metadata_normalizer import normalize_genre_list
from app.services.musicbrainz import find_recording_mbid
from app.utils.artist_normalization import normalize_artist_name

router = APIRouter()

STREAM_TOKEN_EXPIRE_SECONDS = 60


def create_stream_token(track_id: int, user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=STREAM_TOKEN_EXPIRE_SECONDS
    )

    payload = {
        "sub": str(user_id),
        "track_id": track_id,
        "purpose": "mobile_stream",
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )


def verify_stream_token(token: str, track_id: int) -> bool:
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[settings.auth_algorithm],
        )
    except JWTError:
        return False

    if payload.get("purpose") != "mobile_stream":
        return False

    if payload.get("track_id") != track_id:
        return False

    return True


def get_album_artwork_path(db: Session, album_name: str | None) -> str | None:
    if not album_name:
        return None

    album_key = normalize_album_name(album_name)

    if not album_key:
        return None

    artwork = (
        db.query(AlbumArtwork)
        .filter(AlbumArtwork.album_key == album_key)
        .first()
    )

    return artwork.artwork_path if artwork else None


def get_artist_artwork_path(db: Session, artist_name: str | None) -> str | None:
    if not artist_name:
        return None

    artist_key = normalize_artist_name(artist_name)

    if not artist_key:
        return None

    artwork = (
        db.query(ArtistArtwork)
        .filter(ArtistArtwork.artist_key == artist_key)
        .first()
    )

    return artwork.artwork_path if artwork else None


def build_track_response(track: Track, db: Session | None = None) -> TrackResponse:
    album_artwork_path = None
    artist_artwork_path = None

    if db:
        album_artwork_path = get_album_artwork_path(db, track.album)
        artist_artwork_path = get_artist_artwork_path(db, track.artist)

    return TrackResponse(
        id=track.id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        genre=track.genre,
        genres=[item.genre for item in track.track_genres],
        artists=[item.artist_name for item in track.track_artists],
        file_path=track.file_path,
        artwork_path=album_artwork_path,
        album_artwork_path=album_artwork_path,
        artist_artwork_path=artist_artwork_path,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
        raw_album=track.raw_album,
        raw_genre=track.raw_genre,
        musicbrainz_recording_id=track.musicbrainz_recording_id,
        lastfm_tags_enriched=track.lastfm_tags_enriched,
    )


@router.get("/tracks/count", tags=["tracks"])
def get_track_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(func.count(Track.id)).scalar()
    return {"count": count}


@router.get("/tracks", response_model=list[TrackResponse], tags=["tracks"])
def list_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .order_by(Track.artist.asc(), Track.album.asc(), Track.title.asc())
        .all()
    )

    return [build_track_response(track, db) for track in tracks]


@router.get("/tracks/{track_id}/stream", tags=["tracks"])
def stream_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
    )


@router.get("/tracks/{track_id}/mobile-stream-token", tags=["tracks"])
def get_mobile_stream_token(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    return {
        "token": create_stream_token(
            track_id=track.id,
            user_id=current_user.id,
        )
    }


@router.get("/tracks/{track_id}/mobile-stream", tags=["tracks"])
def mobile_stream_track(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.query_params.get("token")

    if not token or not verify_stream_token(token, track_id):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    extension = file_path.suffix.lower()
    mobile_native_extensions = {".mp3", ".m4a", ".aac"}

    if extension in mobile_native_extensions:
        media_type, _ = mimetypes.guess_type(str(file_path))

        return FileResponse(
            path=file_path,
            media_type=media_type or "audio/mpeg",
            filename="mobile-stream.mp3",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    if extension not in {".flac", ".wav", ".aiff", ".aif"}:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported mobile audio format: {extension}",
        )

    cache_dir = Path("data/mobile_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_file_path = cache_dir / f"track_{track.id}.mp3"
    temp_file_path = cache_dir / f"track_{track.id}.tmp.mp3"

    source_mtime = file_path.stat().st_mtime

    cache_is_valid = (
        cached_file_path.exists()
        and cached_file_path.stat().st_size > 0
        and cached_file_path.stat().st_mtime >= source_mtime
    )

    if not cache_is_valid:
        if temp_file_path.exists():
            temp_file_path.unlink()

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(file_path),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "320k",
            "-movflags",
            "+faststart",
            str(temp_file_path),
        ]

        result = subprocess.run(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            if temp_file_path.exists():
                temp_file_path.unlink()

            raise HTTPException(
                status_code=500,
                detail=f"Failed to create mobile stream: {result.stderr.strip()}",
            )

        temp_file_path.replace(cached_file_path)

    return FileResponse(
        path=cached_file_path,
        media_type="audio/mpeg",
        filename="mobile-stream.mp3",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post(
    "/tracks/{track_id}/musicbrainz-recording",
    response_model=TrackResponse,
    tags=["tracks"],
)
def fetch_musicbrainz_recording_id(
    track_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track.musicbrainz_recording_id and not force:
        return build_track_response(track, db)

    mbid = find_recording_mbid(
        track.title,
        track.artist,
        raw_title=track.raw_title,
        raw_artist=track.raw_artist,
    )

    if not mbid:
        raise HTTPException(status_code=404, detail="No MusicBrainz recording match found")

    track.musicbrainz_recording_id = mbid
    db.commit()

    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    return build_track_response(track, db)


@router.post("/tracks/{track_id}/lastfm/now-playing", tags=["tracks"])
def update_track_now_playing_on_lastfm(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = db.query(AppSetting).first()

    if not settings_row:
        raise HTTPException(status_code=400, detail="App settings not found")

    if (
        not settings_row.lastfm_api_key
        or not settings_row.lastfm_api_secret
        or not settings_row.lastfm_session_key
    ):
        raise HTTPException(status_code=400, detail="Missing Last.fm credentials or session")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.title or not track.artist:
        raise HTTPException(status_code=400, detail="Track is missing title or artist")

    result = update_now_playing(
        api_key=settings_row.lastfm_api_key,
        api_secret=settings_row.lastfm_api_secret,
        session_key=settings_row.lastfm_session_key,
        track_name=track.title,
        artist_name=track.artist,
        album_name=track.album,
        mbid=track.musicbrainz_recording_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Last.fm now playing failed")

    return result


@router.post("/tracks/{track_id}/lastfm/scrobble", tags=["tracks"])
def scrobble_track_to_lastfm(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = db.query(AppSetting).first()

    if not settings_row:
        raise HTTPException(status_code=400, detail="App settings not found")

    if (
        not settings_row.lastfm_api_key
        or not settings_row.lastfm_api_secret
        or not settings_row.lastfm_session_key
    ):
        raise HTTPException(status_code=400, detail="Missing Last.fm credentials or session")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.title or not track.artist:
        raise HTTPException(status_code=400, detail="Track is missing title or artist")

    result = scrobble_track(
        api_key=settings_row.lastfm_api_key,
        api_secret=settings_row.lastfm_api_secret,
        session_key=settings_row.lastfm_session_key,
        track_name=track.title,
        artist_name=track.artist,
        album_name=track.album,
        mbid=track.musicbrainz_recording_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"] or "Last.fm scrobble failed")

    return result


@router.delete("/tracks/purge", tags=["tracks"])
def purge_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted_tracks = db.query(Track).count()

    db.query(PlaylistTrack).delete()
    db.query(PlaybackQueueItem).delete()

    session = db.query(PlaybackSession).first()
    if session:
        session.current_track_id = None
        session.queue_index = -1
        session.current_time_seconds = 0
        session.is_playing = False

    db.query(TrackArtist).delete()
    db.query(TrackGenre).delete()
    db.query(Track).delete()

    db.commit()

    return {
        "message": "All stored tracks purged",
        "deleted_count": deleted_tracks,
    }


@router.patch("/tracks/{track_id}", response_model=TrackResponse, tags=["tracks"])
def update_track(
    track_id: int,
    payload: TrackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    track.title = payload.title
    track.artist = payload.artist
    track.album = payload.album

    if payload.genres is not None:
        normalized_genres = normalize_genre_list(", ".join(payload.genres))

        track.genre = normalized_genres[0] if normalized_genres else None

        db.query(TrackGenre).filter(
            TrackGenre.track_id == track.id
        ).delete(synchronize_session=False)

        for genre_name in normalized_genres:
            db.add(
                TrackGenre(
                    track_id=track.id,
                    genre=genre_name,
                )
            )

    db.commit()

    track = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id == track_id)
        .first()
    )

    return build_track_response(track, db)