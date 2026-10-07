"""What an artist leaves behind, and how to tidy it.

There is no artist table. An artist is a name on tracks and credits, plus
two name-keyed rows that outlive those: a picture (`artist_artwork`, with a
file under uploads) and Last.fm similarity rows. A transfer moved the songs
and left both behind; deleting an artist's last track did the same. This
is the one place that knows every such row, so the routes that retire an
artist, or rename one, do it whole.
"""

import os

from sqlalchemy.orm import Session

from app.models.artist_artwork import ArtistArtwork
from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.utils.artist_normalization import normalize_artist_name

ARTIST_ARTWORK_DIR = "data/uploads/artists"


def _artwork_file(artwork_path: str | None) -> str | None:
    if not artwork_path:
        return None
    return os.path.join(ARTIST_ARTWORK_DIR, os.path.basename(artwork_path))


def _remove_file(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def artist_has_tracks(db: Session, name: str) -> bool:
    """Whether any track or credit still names the artist."""
    if db.query(Track.id).filter(Track.artist == name).first() is not None:
        return True
    return db.query(TrackArtist.id).filter(TrackArtist.artist_name == name).first() is not None


def retire_artist(db: Session, name: str) -> dict:
    """Remove what a name with no tracks left behind: its picture (row and
    file) and its similarity rows on either side. Returns what went."""
    key = normalize_artist_name(name)
    if not key:
        return {"artwork": False, "similarity_rows": 0}

    artwork = db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == key).first()
    removed_artwork = False
    if artwork is not None:
        _remove_file(_artwork_file(artwork.artwork_path))
        db.delete(artwork)
        removed_artwork = True

    similarity_rows = (
        db.query(ArtistLastfmSimilarity)
        .filter(
            (ArtistLastfmSimilarity.source_artist_key == key)
            | (ArtistLastfmSimilarity.similar_artist_key == key)
        )
        .delete(synchronize_session=False)
    )

    return {"artwork": removed_artwork, "similarity_rows": int(similarity_rows or 0)}


def carry_artist_over(db: Session, source: str, target: str) -> dict:
    """After the songs have moved from `source` to `target`: the target
    inherits the source's picture if it has none of its own, and the source
    is retired. A transfer into an artist without a picture used to lose the
    one the source had."""
    source_key = normalize_artist_name(source)
    target_key = normalize_artist_name(target)
    if not source_key or not target_key or source_key == target_key:
        return {"artwork": False, "similarity_rows": 0, "artwork_carried": False}

    source_art = db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == source_key).first()
    target_art = db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == target_key).first()

    carried = False
    if source_art is not None and (target_art is None or not target_art.artwork_path):
        if target_art is None:
            source_art.artist_name = target
            source_art.artist_key = target_key
            db.flush()
        else:
            target_art.artwork_path = source_art.artwork_path
            source_art.artwork_path = None
            db.delete(source_art)
            db.flush()
        carried = True

    retired = retire_artist(db, source)
    return {**retired, "artwork_carried": carried}


def rekey_artist(db: Session, old: str, new: str) -> dict:
    """A rename: the picture and similarity rows follow the name. Where the
    new name already has rows of its own, those win and the old ones go."""
    old_key = normalize_artist_name(old)
    new_key = normalize_artist_name(new)
    if not old_key or not new_key or old_key == new_key:
        return {"artwork_moved": False, "similarity_rows_moved": 0}

    artwork_moved = False
    old_art = db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == old_key).first()
    if old_art is not None:
        new_art = db.query(ArtistArtwork).filter(ArtistArtwork.artist_key == new_key).first()
        if new_art is None:
            old_art.artist_name = new
            old_art.artist_key = new_key
            artwork_moved = True
        else:
            if not new_art.artwork_path and old_art.artwork_path:
                new_art.artwork_path = old_art.artwork_path
                old_art.artwork_path = None
                artwork_moved = True
            _remove_file(_artwork_file(old_art.artwork_path))
            db.delete(old_art)
        db.flush()

    moved = 0
    for row in (
        db.query(ArtistLastfmSimilarity)
        .filter(
            (ArtistLastfmSimilarity.source_artist_key == old_key)
            | (ArtistLastfmSimilarity.similar_artist_key == old_key)
        )
        .all()
    ):
        source_key = new_key if row.source_artist_key == old_key else row.source_artist_key
        similar_key = new_key if row.similar_artist_key == old_key else row.similar_artist_key
        clash = (
            db.query(ArtistLastfmSimilarity.id)
            .filter(
                ArtistLastfmSimilarity.source_artist_key == source_key,
                ArtistLastfmSimilarity.similar_artist_key == similar_key,
                ArtistLastfmSimilarity.id != row.id,
            )
            .first()
        )
        if clash is not None or source_key == similar_key:
            db.delete(row)
            continue
        if row.source_artist_key == old_key:
            row.source_artist_key, row.source_artist_name = new_key, new
        if row.similar_artist_key == old_key:
            row.similar_artist_key, row.similar_artist_name = new_key, new
        moved += 1
    db.flush()

    return {"artwork_moved": artwork_moved, "similarity_rows_moved": moved}


def retire_orphan_artists(db: Session) -> dict:
    """Every artwork and similarity row whose name no longer has a track or
    a credit. Run after a cleanup deletes tracks, so an artist whose last
    file went is retired like a transferred one."""
    live_keys: set[str] = set()
    for (name,) in db.query(Track.artist).filter(Track.artist.isnot(None)).distinct().all():
        key = normalize_artist_name(name)
        if key:
            live_keys.add(key)
    for (name,) in db.query(TrackArtist.artist_name).distinct().all():
        key = normalize_artist_name(name)
        if key:
            live_keys.add(key)

    artwork_removed = 0
    for artwork in db.query(ArtistArtwork).all():
        if artwork.artist_key in live_keys:
            continue
        _remove_file(_artwork_file(artwork.artwork_path))
        db.delete(artwork)
        artwork_removed += 1

    # A row is the library artist it was fetched for: its neighbours are
    # often names the library does not hold at all, and those rows are what
    # the Last.fm retriever reads. Only a row whose own artist is gone goes.
    similarity_removed = 0
    for row in db.query(ArtistLastfmSimilarity).all():
        if row.source_artist_key in live_keys:
            continue
        db.delete(row)
        similarity_removed += 1

    db.flush()
    return {"artists_retired": artwork_removed, "similarity_rows": similarity_removed}
