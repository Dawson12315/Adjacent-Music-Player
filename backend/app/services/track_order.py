"""How an album's tracks are ordered, shared by the album and artist routes."""

from sqlalchemy import case, func

from app.models.track import Track


def album_track_order():
    """Disc, then number, then title; unnumbered tracks after numbered ones."""
    return [
        func.coalesce(Track.disc_number, 1),
        case((func.coalesce(Track.track_number, 0) > 0, 0), else_=1),
        func.coalesce(Track.track_number, 0),
        func.lower(Track.title),
    ]
