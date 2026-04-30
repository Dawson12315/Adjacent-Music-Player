from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin
from app.models.track import Track
from app.models.user import User
from app.schemas.artist_edit import ArtistRenameRequest, ArtistTransferRequest

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

    db.commit()

    return {
        "message": "Artist renamed successfully",
        "updated_tracks": len(tracks),
        "artist": new_artist,
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

    db.commit()

    return {
        "message": "Artist transferred successfully",
        "moved_tracks": len(source_tracks),
        "artist": target_artist,
    }