"""Radio: a seed, a memory, and "what next" in batches.

A station is made from one track, one album or one artist. It pools from
the same recommender the playlist suggestions and the For you rail use,
and only decides three things of its own:

- the seeds: the one track; every track on the album; or a sample of the
  artist's catalogue, the tracks this listener plays most first;
- the blend: how much of a batch is the seed's own material (the seed
  artist's other tracks, the album's own tracks, the artist's catalogue)
  against neighbours the recommender found. Track and album radio keep a
  fifth; artist radio keeps a quarter, which is what makes it feel like
  that artist's station without turning into a shuffle of their records;
- the memory: what the station has played lately stays out, so it does not
  come back round too soon. When the library cannot fill a batch the
  memory is relaxed, then the seed's genres are drawn at random, and the
  batch is marked thin so the client can say so.

Track radio opens with the seed itself. Album and artist radio open with
one of their own, so the station announces what it is.
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.radio_station import RadioStation, RadioStationPlay
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.models.track_user_stats import TrackUserStats
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)
from app.services.track_order import album_track_order
from app.services.track_responses import record_artist_expr

BATCH = 20
# Forty is enough to blend from; the recommender retrieves twenty times
# this and walks the lot once per pick, so the pool is the cost of a batch.
CANDIDATE_POOL = 40
# How much of a batch is the seed's own material, per seed type.
OWN_SHARE = {"track": 4, "album": 4, "artist": 5}
# How many of the artist's tracks seed the recommender: enough to carry the
# vibe, few enough that a huge catalogue does not swamp the channels.
ARTIST_SEED_SAMPLE = 40
MEMORY = 200
MEMORY_RELAXED = 50
RECENT_STATIONS = 12


# ------------------------------------------------------------------ stations


def seed_key_for(seed_type: str, *, track_id=None, album=None, album_artist=None, artist=None) -> str:
    if seed_type == "track":
        return f"track:{int(track_id)}"
    if seed_type == "album":
        return f"album:{(album or '').strip().lower()}|{(album_artist or '').strip().lower()}"
    return f"artist:{(artist or '').strip().lower()}"


def station_name(seed_type: str, *, track=None, album=None, artist=None) -> str:
    if seed_type == "track":
        return f"{(track.title if track else None) or 'Track'} radio"
    if seed_type == "album":
        return f"{album or 'Album'} radio"
    return f"{artist or 'Artist'} radio"


def get_or_create_station(db: Session, user_id: int, payload) -> RadioStation | None:
    """The listener's station for this seed, made if it did not exist.

    None when the seed names nothing in the library: a deleted track, an
    album or artist with no tracks.
    """
    seed_type = payload.seed_type
    seed_track = None
    if seed_type == "track":
        if payload.seed_track_id is None:
            return None
        seed_track = db.query(Track).filter(Track.id == payload.seed_track_id).first()
        if seed_track is None:
            return None
        key = seed_key_for("track", track_id=seed_track.id)
        name = station_name("track", track=seed_track)
    elif seed_type == "album":
        if not payload.seed_album:
            return None
        if not _album_tracks_query(db, payload.seed_album, payload.seed_album_artist).first():
            return None
        key = seed_key_for("album", album=payload.seed_album, album_artist=payload.seed_album_artist)
        name = station_name("album", album=payload.seed_album)
    else:
        if not payload.seed_artist:
            return None
        if not _artist_tracks_query(db, payload.seed_artist).first():
            return None
        key = seed_key_for("artist", artist=payload.seed_artist)
        name = station_name("artist", artist=payload.seed_artist)

    station = (
        db.query(RadioStation)
        .filter(RadioStation.user_id == user_id, RadioStation.seed_key == key)
        .first()
    )
    now = datetime.utcnow()
    if station is None:
        station = RadioStation(
            user_id=user_id,
            seed_type=seed_type,
            seed_track_id=seed_track.id if seed_track else None,
            seed_album=payload.seed_album if seed_type == "album" else None,
            seed_album_artist=payload.seed_album_artist if seed_type == "album" else None,
            seed_artist=payload.seed_artist if seed_type == "artist" else None,
            seed_key=key,
            name=name,
            created_at=now,
            last_played_at=now,
        )
        db.add(station)
    else:
        station.name = name
        station.last_played_at = now
    db.commit()
    db.refresh(station)
    return station


def recent_stations(db: Session, user_id: int, limit: int = RECENT_STATIONS) -> list[RadioStation]:
    return (
        db.query(RadioStation)
        .filter(RadioStation.user_id == user_id)
        .order_by(RadioStation.last_played_at.desc(), RadioStation.id.desc())
        .limit(limit)
        .all()
    )


def delete_station(db: Session, station: RadioStation) -> None:
    db.query(RadioStationPlay).filter(RadioStationPlay.station_id == station.id).delete(
        synchronize_session=False
    )
    db.delete(station)
    db.commit()


# --------------------------------------------------------------------- seeds


def _album_tracks_query(db: Session, album: str, album_artist: str | None):
    query = (
        db.query(Track)
        .options(selectinload(Track.track_artists), selectinload(Track.track_genres))
        .filter(func.lower(Track.album) == album.strip().lower())
    )
    if album_artist:
        query = query.filter(func.lower(record_artist_expr()) == album_artist.strip().lower())
    return query.order_by(*album_track_order())


def _artist_tracks_query(db: Session, artist: str):
    return (
        db.query(Track)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .options(selectinload(Track.track_artists), selectinload(Track.track_genres))
        .filter(func.lower(TrackArtist.artist_name) == artist.strip().lower())
    )


def _by_listener_affinity(db: Session, user_id: int, tracks: list[Track]) -> list[Track]:
    """The tracks this listener plays and keeps, first; the rest shuffled."""
    if not tracks:
        return []
    ids = [track.id for track in tracks]
    rows = (
        db.query(TrackUserStats)
        .filter(TrackUserStats.user_id == user_id, TrackUserStats.track_id.in_(ids))
        .all()
    )
    score = {
        row.track_id: (row.like_count or 0) * 5
        + (row.play_count or 0) * 1.5
        + (row.completion_count or 0) * 2
        - (row.skip_count or 0) * 1.5
        for row in rows
    }
    shuffled = list(tracks)
    random.shuffle(shuffled)
    return sorted(shuffled, key=lambda track: -score.get(track.id, 0.0))


def seed_tracks(db: Session, station: RadioStation, user_id: int) -> list[Track]:
    """What the station is made from, as tracks."""
    if station.seed_type == "track":
        track = (
            db.query(Track)
            .options(selectinload(Track.track_artists), selectinload(Track.track_genres))
            .filter(Track.id == station.seed_track_id)
            .first()
        )
        return [track] if track else []
    if station.seed_type == "album":
        return _album_tracks_query(db, station.seed_album or "", station.seed_album_artist).all()
    catalogue = _artist_tracks_query(db, station.seed_artist or "").all()
    return _by_listener_affinity(db, user_id, catalogue)[:ARTIST_SEED_SAMPLE]


def own_pool(db: Session, station: RadioStation, user_id: int, seeds: list[Track]) -> list[Track]:
    """The seed's own material, best first: the seed artist's other tracks,
    the album's tracks, or the artist's catalogue."""
    if station.seed_type == "track":
        seed = seeds[0] if seeds else None
        if seed is None:
            return []
        names = [credit.artist_name for credit in (seed.track_artists or []) if credit.artist_name]
        if not names and seed.artist:
            names = [seed.artist]
        pool: dict[int, Track] = {}
        for name in names[:2]:
            for track in _artist_tracks_query(db, name).all():
                if track.id != seed.id:
                    pool[track.id] = track
        return _by_listener_affinity(db, user_id, list(pool.values()))
    if station.seed_type == "album":
        return _by_listener_affinity(db, user_id, list(seeds))
    return _by_listener_affinity(db, user_id, _artist_tracks_query(db, station.seed_artist or "").all())


def _own_name(station: RadioStation, seeds: list[Track]) -> str:
    if station.seed_type == "track":
        seed = seeds[0] if seeds else None
        return (seed.artist if seed else None) or "this artist"
    if station.seed_type == "album":
        return station.seed_album or "this album"
    return station.seed_artist or "this artist"


# -------------------------------------------------------------------- memory


def remembered_track_ids(db: Session, station: RadioStation, limit: int = MEMORY) -> list[int]:
    rows = (
        db.query(RadioStationPlay.track_id)
        .filter(RadioStationPlay.station_id == station.id)
        .order_by(RadioStationPlay.played_at.desc(), RadioStationPlay.id.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def record_plays(db: Session, station: RadioStation, track_ids: list[int]) -> None:
    now = datetime.utcnow()
    for offset, track_id in enumerate(dict.fromkeys(int(track_id) for track_id in track_ids)):
        db.add(RadioStationPlay(station_id=station.id, track_id=track_id, played_at=now))
    station.last_played_at = now
    db.flush()

    keep = (
        db.query(RadioStationPlay.id)
        .filter(RadioStationPlay.station_id == station.id)
        .order_by(RadioStationPlay.played_at.desc(), RadioStationPlay.id.desc())
        .limit(MEMORY)
        .all()
    )
    keep_ids = [row[0] for row in keep]
    if keep_ids:
        db.query(RadioStationPlay).filter(
            RadioStationPlay.station_id == station.id,
            RadioStationPlay.id.notin_(keep_ids),
        ).delete(synchronize_session=False)
    db.commit()


# ---------------------------------------------------------------------- next


def _recommend(db, seed_ids, user_id, excluded, limit):
    """(track_id, reason) pairs from the recommender, in its order."""
    answer = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_ids,
        debug=True,
        playlist_id=None,
        limit=limit,
        exclude_track_ids=list(excluded),
        user_id=user_id,
        include_recent_additions=False,
        allow_genre_relaxation=True,
        exclude_from_retrieval=True,
    )
    if not isinstance(answer, dict):
        return []
    pairs = []
    for item in answer.get("recommendations", []):
        track = item.get("track") or {}
        track_id = track.get("id")
        if track_id is None:
            continue
        reason = (item.get("debug") or {}).get("reason_summary")
        pairs.append((int(track_id), reason))
    return pairs


def _genre_fallback(db, seeds: list[Track], excluded: set[int], limit: int) -> list[int]:
    """Random tracks sharing a genre with the seeds, for a library that has
    nothing better to say."""
    genres = set()
    for seed in seeds:
        for item in seed.track_genres or []:
            if item.genre:
                genres.add(item.genre)
        if seed.genre:
            genres.add(seed.genre)
    if not genres or limit <= 0:
        return []
    query = (
        db.query(Track.id)
        .outerjoin(TrackGenre, TrackGenre.track_id == Track.id)
        .filter((TrackGenre.genre.in_(genres)) | (Track.genre.in_(genres)))
    )
    if excluded:
        query = query.filter(Track.id.notin_(excluded))
    # Distinct ids, shuffled here: Postgres will not ORDER BY random() over
    # a DISTINCT select.
    ids = [row[0] for row in query.distinct().limit(500).all()]
    random.shuffle(ids)
    return ids[:limit]


def _interleave(own: list, others: list) -> list:
    """Spread the own tracks evenly through the others."""
    if not own:
        return list(others)
    if not others:
        return list(own)
    total = len(own) + len(others)
    step = total / len(own)
    result = []
    own_iter = iter(own)
    other_iter = iter(others)
    next_own_at = step / 2
    for position in range(total):
        if position >= next_own_at and own_iter is not None:
            item = next(own_iter, None)
            if item is not None:
                result.append(item)
                next_own_at += step
                continue
            own_iter = None
        item = next(other_iter, None)
        if item is not None:
            result.append(item)
        else:
            item = next(own_iter, None) if own_iter is not None else None
            if item is not None:
                result.append(item)
    return result


def next_batch(
    db: Session,
    station: RadioStation,
    user_id: int,
    limit: int = BATCH,
    exclude_track_ids: list[int] | None = None,
) -> tuple[list[tuple[int, str | None]], bool]:
    """The station's next `limit` tracks as (track_id, reason) pairs, and
    whether the library ran thin to make them."""
    limit = max(1, min(int(limit or BATCH), 50))
    seeds = seed_tracks(db, station, user_id)
    if not seeds:
        return [], True

    seed_ids = [track.id for track in seeds]
    memory = remembered_track_ids(db, station)
    first_batch = not memory and not exclude_track_ids
    client_excluded = set(int(track_id) for track_id in (exclude_track_ids or []))
    own_name = _own_name(station, seeds)
    own_share = OWN_SHARE.get(station.seed_type, 4)

    def build(memory_ids: list[int]):
        excluded = set(memory_ids) | client_excluded
        if station.seed_type == "track":
            excluded |= set(seed_ids)
        pairs = _recommend(db, seed_ids, user_id, excluded, CANDIDATE_POOL)
        own_candidates = own_pool(db, station, user_id, seeds)
        own_ids = {track.id for track in own_candidates}

        chosen_own: list[tuple[int, str | None]] = []
        neighbours: list[tuple[int, str | None]] = []
        seen: set[int] = set()
        for track_id, reason in pairs:
            if track_id in seen or track_id in excluded:
                continue
            seen.add(track_id)
            if track_id in own_ids:
                chosen_own.append((track_id, f"From {own_name}"))
            else:
                neighbours.append((track_id, reason or f"Because it belongs with {own_name}"))
        for track in own_candidates:
            if track.id in seen or track.id in excluded:
                continue
            seen.add(track.id)
            chosen_own.append((track.id, f"From {own_name}"))

        opener: list[tuple[int, str | None]] = []
        want = limit
        if first_batch:
            if station.seed_type == "track":
                opener = [(seed_ids[0], "The track you started from")]
            elif chosen_own:
                opener = [chosen_own.pop(0)]
            want -= len(opener)

        # The opener counts toward the album's or artist's share; the seed
        # track is the station itself, not its artist's share.
        own_quota = own_share - (len(opener) if station.seed_type != "track" else 0)
        own_take = min(max(0, own_quota), len(chosen_own), want)
        others_take = min(len(neighbours), want - own_take)
        # Short of neighbours: the seed's own material fills in.
        own_take = min(len(chosen_own), want - others_take)
        body = _interleave(chosen_own[:own_take], neighbours[:others_take])
        return opener + body, excluded

    batch, excluded = build(memory)
    thin = False
    if len(batch) < limit and len(memory) > MEMORY_RELAXED:
        batch, excluded = build(memory[:MEMORY_RELAXED])
    if len(batch) < limit:
        thin = True
        have = {track_id for track_id, _ in batch}
        for track_id in _genre_fallback(db, seeds, excluded | have, limit - len(batch)):
            batch.append((track_id, f"Shares a genre with {own_name}"))
            have.add(track_id)
    if len(batch) < limit:
        # The station has played everything its corner of the library holds.
        # Radio keeps going: the memory is set aside and the genre pool comes
        # round again, keeping out only what the client is still holding.
        for track_id in _genre_fallback(db, seeds, client_excluded | have, limit - len(batch)):
            batch.append((track_id, f"Back around to {own_name}"))
            have.add(track_id)
    return batch[:limit], thin
