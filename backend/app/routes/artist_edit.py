from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.user import User
from app.schemas.artist_edit import ArtistRenameRequest, ArtistTransferRequest
from app.services.artist_identity import carry_artist_over, rekey_artist
from app.services.recommendations.rec_cache import invalidate_library_caches

router = APIRouter()


@router.patch("/artists/rename", tags=["artists"])
def rename_artist(
    payload: ArtistRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    current_artist = payload.current_artist.strip()
    new_artist = payload.new_artist.strip()

    if not current_artist or not new_artist:
        raise HTTPException(status_code=400, detail="Artist names cannot be empty")

    tracks = db.query(Track).filter(Track.artist == current_artist).all()

    if not tracks:
        raise HTTPException(status_code=404, detail="Artist not found")

    for track in tracks:
        track.artist = new_artist

    # The index reads track_artists; rename the credit rows too, or the old
    # name keeps its page and the new one has none. One credit at a time:
    # a track already crediting the new name would collide with the unique
    # (track, name) pair under a bulk update.
    for credit in db.query(TrackArtist).filter(TrackArtist.artist_name == current_artist).all():
        clash = (
            db.query(TrackArtist.id)
            .filter(
                TrackArtist.track_id == credit.track_id,
                TrackArtist.artist_name == new_artist,
                TrackArtist.id != credit.id,
            )
            .first()
        )
        if clash is not None:
            db.delete(credit)
        else:
            credit.artist_name = new_artist

    # The picture and the similarity rows follow the name.
    followed = rekey_artist(db, current_artist, new_artist)

    db.commit()
    invalidate_library_caches()

    return {
        "message": "Artist renamed successfully",
        "updated_tracks": len(tracks),
        "artist": new_artist,
        **followed,
    }


@router.patch("/artists/transfer", tags=["artists"])
def transfer_artist(
    payload: ArtistTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    source_artist = payload.source_artist.strip()
    target_artist = payload.target_artist.strip()

    if not source_artist or not target_artist:
        raise HTTPException(status_code=400, detail="Artist names cannot be empty")

    if source_artist == target_artist:
        raise HTTPException(status_code=400, detail="Source and target artist must be different")

    source_tracks = db.query(Track).filter(Track.artist == source_artist).all()

    if not source_tracks:
        raise HTTPException(status_code=404, detail="Source artist not found")

    target_tracks_exist = db.query(Track).filter(Track.artist == target_artist).first()

    if not target_tracks_exist:
        raise HTTPException(status_code=404, detail="Target artist not found")

    for track in source_tracks:
        track.artist = target_artist

    # Credits already naming the target on the same track would collide with
    # the unique (track, name) pair; drop those, then rename the rest.
    source_credits = db.query(TrackArtist).filter(TrackArtist.artist_name == source_artist).all()
    for credit in source_credits:
        clash = (
            db.query(TrackArtist)
            .filter(
                TrackArtist.track_id == credit.track_id,
                TrackArtist.artist_name == target_artist,
                TrackArtist.id != credit.id,
            )
            .first()
        )
        if clash is not None:
            db.delete(credit)
        else:
            credit.artist_name = target_artist

    # The source has no songs now. Its picture goes to the target if the
    # target has none, and everything else it left behind is removed — the
    # artwork row and file and the similarity rows used to outlive it.
    retired = carry_artist_over(db, source_artist, target_artist)

    db.commit()
    invalidate_library_caches()

    return {
        "message": "Artist transferred successfully",
        "retired": retired,
        "moved_tracks": len(source_tracks),
        "artist": target_artist,
    }