"""Radio: a seed, a memory, and "what next" in batches.

A station is made from one track, one album or one artist. It pools from
the same recommender the playlist suggestions and the For you rail use,
and only decides a few things of its own:

- the seeds: the one track; every track on the album; or a sample of the
  artist's catalogue, the tracks this listener plays most first — plus any
  track the listener marked "more like this" on the station;
- the blend: how much of a batch is the seed's own material (the seed
  artist's other tracks, the album's own tracks, the artist's catalogue)
  against neighbours the recommender found. Track and album radio keep a
  fifth; artist radio keeps a quarter, which is what makes it feel like
  that artist's station without turning into a shuffle of their records;
- the variety: no artist takes more than a few neighbour slots in a batch,
  and no artist plays twice in a row;
- the memory: what the station has played lately, and what it has handed
  out lately, stays out, so nothing comes back round too soon. When the
  library cannot fill a batch the station reaches wider — the seeds'
  genres, the seed artist's genres, what the listener plays most, then the
  library at large — and the batch says how far it reached. A station never
  falls silent while the library has something the client is not holding.

Track radio opens with the seed itself. Album radio opens with track one;
artist radio opens with the track of theirs the listener plays most.

Radio only seeds and feeds the recommender; it never changes how a track
is scored.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.radio_station import RadioStation, RadioStationFeedback, RadioStationPlay
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.models.track_user_stats import TrackUserStats
from app.services.recommendations.genre_utils import (
    get_track_families,
    is_non_genre_tag,
    map_genre_to_family,
)
from app.services.recommendations.playlist_recommender import (
    get_playlist_recommendations_from_track_ids,
)
from app.services.recommendations.retrievers.genre_retriever import get_genre_family_map
from app.services.track_order import album_track_order
from app.services.track_responses import record_artist_expr
from app.utils.artist_normalization import normalize_artist_name

BATCH = 20
# Forty is enough to blend from, artist caps included: a bigger pool only
# brings more of the same artists, and the recommender retrieves twenty
# times this and walks the lot once per pick, so the pool is the cost of a
# batch (measured: 40 -> 170 ms, 80 -> 550 ms on a 36k-track library, same
# variety).
CANDIDATE_POOL = 40
# How much of a batch is the seed's own material, per seed type.
OWN_SHARE = {"track": 4, "album": 4, "artist": 5}
# Short of neighbours, own material may fill in this far past its share;
# past that the station reaches wider rather than turning into a shuffle of
# the seed.
OWN_BACKFILL = 2
# How many neighbour slots one artist may take in a batch. The listener's
# favourite artists stay prominent; they do not become the whole station.
NEIGHBOUR_ARTIST_CAP = 3
# How many of the artist's tracks seed the recommender: enough to carry the
# vibe, few enough that a huge catalogue does not swamp the channels.
ARTIST_SEED_SAMPLE = 40
# How many "more like this" tracks join the seeds, newest first.
EXTRA_SEEDS = 10
MEMORY = 200
MEMORY_RELAXED = 50
RECENT_STATIONS = 12
# How long a station keeps its lineup, so coming back continues it; and how
# much of the lineup is kept, the newest end. The lineup is also what the
# station has handed out lately, kept out of the next batch whether or not
# the client got round to reporting it.
LINEUP_DAYS = 10
LINEUP_MAX = 200

# What the listener can say about a track on a station.
FEEDBACK_MORE = "more"
FEEDBACK_LESS = "less"
FEEDBACK_LESS_ARTIST = "less_artist"
FEEDBACK_KINDS = (FEEDBACK_MORE, FEEDBACK_LESS, FEEDBACK_LESS_ARTIST)

# How far a batch had to reach, widest step last.
REACH_GENRE = "genre"
REACH_ARTIST = "artist"
REACH_LISTENER = "listener"
REACH_LIBRARY = "library"
REACH_AGAIN = "again"

# Family names as a reason line says them.
FAMILY_LABELS = {
    "rock_alt": "rock",
    "hip_hop": "hip hop",
    "rnb_soul": "R&B",
    "dance_electronic": "electronic",
    "country_folk": "country",
    "jazz_blues": "jazz and blues",
    "classical_score": "score",
    "ambient_chill": "ambient",
    "reggae_dancehall": "reggae",
    "gospel_spiritual": "gospel",
}


class SeedGone(Exception):
    """The station's seed names nothing in the library any more."""


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


def _find_station(db: Session, user_id: int, key: str) -> RadioStation | None:
    return (
        db.query(RadioStation)
        .filter(RadioStation.user_id == user_id, RadioStation.seed_key == key)
        .first()
    )


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

    station = _find_station(db, user_id, key)
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
        try:
            db.commit()
        except IntegrityError:
            # Two devices started the same station at once; the other insert
            # won, and this one wants that row.
            db.rollback()
            station = _find_station(db, user_id, key)
            if station is None:
                raise
            station.last_played_at = now
            db.commit()
    else:
        # A renamed seed renames the station; a different casing of the same
        # seed does not.
        if (station.name or "").lower() != name.lower():
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


# -------------------------------------------------------------------- lineup


def lineup_of(station: RadioStation, now: datetime | None = None) -> list[dict]:
    """The station's lineup as [{track_id, reason}], or [] once it has aged out."""
    if not station.lineup_json or not station.lineup_saved_at:
        return []
    now = now or datetime.utcnow()
    if station.lineup_saved_at < now - timedelta(days=LINEUP_DAYS):
        return []
    try:
        rows = json.loads(station.lineup_json)
    except (TypeError, ValueError):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("track_id") is not None]


def extend_lineup(db: Session, station: RadioStation, pairs: list[tuple[int, str | None]]) -> None:
    """Add a handed-out batch to the lineup. An aged-out lineup starts over.

    Trimmed to the newest LINEUP_MAX entries, keeping the position pointing
    at the same track.
    """
    now = datetime.utcnow()
    rows = lineup_of(station, now)
    position = (station.lineup_position or 0) if rows else 0
    rows = rows + [{"track_id": int(track_id), "reason": reason} for track_id, reason in pairs]
    if len(rows) > LINEUP_MAX:
        cut = len(rows) - LINEUP_MAX
        rows = rows[cut:]
        position = max(0, position - cut)
    station.lineup_json = json.dumps(rows)
    station.lineup_position = min(position, max(0, len(rows) - 1))
    station.lineup_saved_at = now
    db.commit()


def remaining_lineup(station: RadioStation) -> list[tuple[int, str | None]]:
    """The lineup from the track the listener got to, onward."""
    rows = lineup_of(station)
    if not rows:
        return []
    position = min(max(0, station.lineup_position or 0), len(rows) - 1)
    return [(int(row["track_id"]), row.get("reason")) for row in rows[position:]]


def _advance_lineup(station: RadioStation, track_ids: list[int]) -> None:
    """The listener reached these tracks: the position moves to the furthest
    of them, looking forward from where the listener is, so a track the
    station handed out twice lands on its next appearance rather than its
    last. Behind the position (the listener went back), the nearest
    earlier appearance."""
    rows = lineup_of(station)
    if not rows:
        return
    wanted = {int(track_id) for track_id in track_ids}
    position = min(max(0, station.lineup_position or 0), len(rows) - 1)
    ahead = {}
    for index in range(position, len(rows)):
        track_id = int(rows[index]["track_id"])
        if track_id in wanted and track_id not in ahead:
            ahead[track_id] = index
    if ahead:
        station.lineup_position = max(ahead.values())
        station.lineup_saved_at = datetime.utcnow()
        return
    for index in range(position - 1, -1, -1):
        if int(rows[index]["track_id"]) in wanted:
            station.lineup_position = index
            station.lineup_saved_at = datetime.utcnow()
            return


def delete_station(db: Session, station: RadioStation) -> None:
    db.query(RadioStationPlay).filter(RadioStationPlay.station_id == station.id).delete(
        synchronize_session=False
    )
    db.query(RadioStationFeedback).filter(RadioStationFeedback.station_id == station.id).delete(
        synchronize_session=False
    )
    db.delete(station)
    db.commit()


# ------------------------------------------------------------------ feedback


def station_feedback(db: Session, station: RadioStation) -> dict:
    """What the listener has said about this station: {more: [track ids,
    newest first], less: {track ids}, less_artists: {key: name}}."""
    rows = (
        db.query(RadioStationFeedback)
        .filter(RadioStationFeedback.station_id == station.id)
        .order_by(RadioStationFeedback.created_at.desc(), RadioStationFeedback.id.desc())
        .all()
    )
    more: list[int] = []
    less: set[int] = set()
    less_artists: dict[str, str] = {}
    for row in rows:
        if row.kind == FEEDBACK_MORE and row.track_id is not None:
            more.append(int(row.track_id))
        elif row.kind == FEEDBACK_LESS and row.track_id is not None:
            less.add(int(row.track_id))
        elif row.kind == FEEDBACK_LESS_ARTIST and row.artist_key:
            less_artists.setdefault(row.artist_key, row.artist_name or row.artist_key)
    return {"more": more, "less": less, "less_artists": less_artists}


def set_feedback(db: Session, station: RadioStation, kind: str, track: Track) -> None:
    """Record one thing the listener said. "More" and "less" on the same
    track replace each other."""
    now = datetime.utcnow()
    if kind in (FEEDBACK_MORE, FEEDBACK_LESS):
        db.query(RadioStationFeedback).filter(
            RadioStationFeedback.station_id == station.id,
            RadioStationFeedback.track_id == track.id,
            RadioStationFeedback.kind.in_([FEEDBACK_MORE, FEEDBACK_LESS]),
        ).delete(synchronize_session=False)
        db.add(RadioStationFeedback(station_id=station.id, track_id=track.id, kind=kind, created_at=now))
    else:
        key = normalize_artist_name(track.artist or "")
        exists = (
            db.query(RadioStationFeedback.id)
            .filter(
                RadioStationFeedback.station_id == station.id,
                RadioStationFeedback.kind == FEEDBACK_LESS_ARTIST,
                RadioStationFeedback.artist_key == key,
            )
            .first()
        )
        if not exists:
            db.add(
                RadioStationFeedback(
                    station_id=station.id,
                    track_id=track.id,
                    kind=kind,
                    artist_key=key,
                    artist_name=track.artist,
                    created_at=now,
                )
            )
    db.commit()


def clear_feedback(db: Session, station: RadioStation, kind: str, track: Track) -> None:
    query = db.query(RadioStationFeedback).filter(
        RadioStationFeedback.station_id == station.id, RadioStationFeedback.kind == kind
    )
    if kind == FEEDBACK_LESS_ARTIST:
        query = query.filter(RadioStationFeedback.artist_key == normalize_artist_name(track.artist or ""))
    else:
        query = query.filter(RadioStationFeedback.track_id == track.id)
    query.delete(synchronize_session=False)
    db.commit()


def artist_is_own(station: RadioStation, artist: str | None) -> bool:
    """Whether this artist is the station itself: the artist of artist
    radio, or the seed's artist on track and album radio. "Less of them"
    would empty the station."""
    key = normalize_artist_name(artist or "")
    if not key:
        return False
    if station.seed_type == "artist":
        return key == normalize_artist_name(station.seed_artist or "")
    if station.seed_type == "album":
        return key == normalize_artist_name(station.seed_album_artist or "")
    return False


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


class Material:
    """What a station is made from, loaded once per batch: the seeds, the
    seed's own material best first, and what to call each own track."""

    def __init__(self, seeds: list[Track], own: list[Track], own_label: dict[int, str], own_name: str):
        self.seeds = seeds
        self.own = own
        self.own_label = own_label
        self.own_name = own_name


def load_material(db: Session, station: RadioStation, user_id: int) -> Material:
    if station.seed_type == "track":
        seed = (
            db.query(Track)
            .options(selectinload(Track.track_artists), selectinload(Track.track_genres))
            .filter(Track.id == station.seed_track_id)
            .first()
        )
        if seed is None:
            return Material([], [], {}, "this artist")
        names = [credit.artist_name for credit in (seed.track_artists or []) if credit.artist_name]
        if not names and seed.artist:
            names = [seed.artist]
        pool: dict[int, Track] = {}
        label: dict[int, str] = {}
        for name in names[:2]:
            for track in _artist_tracks_query(db, name).all():
                if track.id != seed.id and track.id not in pool:
                    pool[track.id] = track
                    label[track.id] = f"From {name}"
        return Material([seed], _by_listener_affinity(db, user_id, list(pool.values())), label, seed.artist or "this artist")

    if station.seed_type == "album":
        # Album order: the station opens with track one and the album's own
        # tracks come round in order.
        tracks = _album_tracks_query(db, station.seed_album or "", station.seed_album_artist).all()
        name = station.seed_album or "this album"
        return Material(tracks, list(tracks), {track.id: f"From {name}" for track in tracks}, name)

    catalogue = _by_listener_affinity(db, user_id, _artist_tracks_query(db, station.seed_artist or "").all())
    name = station.seed_artist or "this artist"
    return Material(catalogue[:ARTIST_SEED_SAMPLE], catalogue, {track.id: f"From {name}" for track in catalogue}, name)


def seed_tracks(db: Session, station: RadioStation, user_id: int) -> list[Track]:
    """What the station is made from, as tracks."""
    return load_material(db, station, user_id).seeds


def own_pool(db: Session, station: RadioStation, user_id: int, seeds=None) -> list[Track]:
    """The seed's own material, best first."""
    return load_material(db, station, user_id).own


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


def record_plays(db: Session, station: RadioStation, track_ids: list[int]) -> int:
    """The client says these played. Only tracks the library has count, and
    a track already remembered moves to the front rather than doubling up,
    so the memory is MEMORY distinct tracks. Returns how many were taken."""
    wanted = list(dict.fromkeys(int(track_id) for track_id in track_ids))
    existing: set[int] = set()
    if wanted:
        existing = {row[0] for row in db.query(Track.id).filter(Track.id.in_(wanted)).all()}
    taken = [track_id for track_id in wanted if track_id in existing]
    now = datetime.utcnow()
    if taken:
        db.query(RadioStationPlay).filter(
            RadioStationPlay.station_id == station.id, RadioStationPlay.track_id.in_(taken)
        ).delete(synchronize_session=False)
        for track_id in taken:
            db.add(RadioStationPlay(station_id=station.id, track_id=track_id, played_at=now))
        _advance_lineup(station, taken)
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
    return len(taken)


# ---------------------------------------------------------------------- next


def _recommend(db, seed_ids, user_id, excluded, limit, refresh=0):
    """Candidates from the recommender, in its order, as {id, artist, debug}."""
    answer = get_playlist_recommendations_from_track_ids(
        db=db,
        seed_track_ids=seed_ids,
        debug=True,
        refresh=refresh,
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
    candidates = []
    for item in answer.get("recommendations", []):
        track = item.get("track") or {}
        track_id = track.get("id")
        if track_id is None:
            continue
        candidates.append({"id": int(track_id), "artist": track.get("artist"), "debug": item.get("debug") or {}})
    return candidates


def _family_label(family: str) -> str:
    return FAMILY_LABELS.get(family, family.replace("_", " "))


def _neighbour_reason(candidate: dict, own_name: str) -> str:
    """Why the station chose a neighbour, in the station's own words, from
    which of the recommender's channels found it."""
    debug = candidate.get("debug") or {}
    sources = debug.get("retrieval_sources") or {}
    families = debug.get("shared_families") or []
    if (sources.get("lastfm_track") or 0) > 0 or (sources.get("lastfm_artist") or 0) > 0:
        return f"Similar to {own_name}"
    if (sources.get("cooccurrence") or 0) > 0:
        return f"Often played around {own_name}"
    if (sources.get("behavior") or 0) > 0:
        artist = candidate.get("artist")
        return f"Close to {own_name}, and you play {artist}" if artist else f"Close to {own_name}, from what you play"
    if families:
        return f"Shares {_family_label(families[0])} with {own_name}"
    return f"Close to {own_name}"


def _families_of(tracks: list[Track]) -> set[str]:
    families: set[str] = set()
    for track in tracks:
        families.update(get_track_families(track))
    return families


def _chunks(items: list, size: int = 400):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _ids_in_families(db: Session, families: set[str]) -> list[int]:
    """Every track in these genre families, by way of the library's genre
    strings (a few hundred) rather than a scan of the tracks."""
    if not families:
        return []
    raw = [genre for genre, family in get_genre_family_map(db).items() if family in families]
    ids: set[int] = set()
    for chunk in _chunks(raw):
        ids.update(row[0] for row in db.query(TrackGenre.track_id).filter(TrackGenre.genre.in_(chunk)).all())
        ids.update(row[0] for row in db.query(Track.id).filter(Track.genre.in_(chunk)).all())
    return list(ids)


def _listener_families(db: Session, user_id: int, top: int = 3) -> set[str]:
    """The genre families this listener plays most."""
    rows = (
        db.query(TrackGenre.genre, func.sum(TrackUserStats.play_count))
        .join(TrackUserStats, TrackUserStats.track_id == TrackGenre.track_id)
        .filter(TrackUserStats.user_id == user_id)
        .group_by(TrackGenre.genre)
        .all()
    )
    weights: Counter = Counter()
    for genre, plays in rows:
        if not genre or is_non_genre_tag(genre):
            continue
        weights[map_genre_to_family(genre)] += float(plays or 0)
    return {family for family, _ in weights.most_common(top)}


def _library_ids(db: Session) -> list[int]:
    return [row[0] for row in db.query(Track.id).all()]


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


def _spread_artists(rows: list[tuple[int, str | None]], artist_of: dict[int, str]) -> list[tuple[int, str | None]]:
    """No artist twice in a row where a swap further down can avoid it. The
    first row stays where it is: it is the opener."""
    rows = list(rows)
    for index in range(1, len(rows)):
        previous = artist_of.get(rows[index - 1][0])
        if not previous or artist_of.get(rows[index][0]) != previous:
            continue
        for later in range(index + 1, len(rows)):
            if artist_of.get(rows[later][0]) != previous:
                rows[index], rows[later] = rows[later], rows[index]
                break
    return rows


def _widen(
    db: Session,
    pool_ids: list[int],
    keep_out: set[int],
    less_artists: set[str],
    per_artist: Counter,
    need: int,
) -> list[tuple[int, str]]:
    """Up to `need` tracks drawn at random from a pool, keeping the artist
    caps. Returns (track_id, artist) pairs."""
    if need <= 0:
        return []
    pool = [track_id for track_id in pool_ids if track_id not in keep_out]
    if not pool:
        return []
    sample = random.sample(pool, min(len(pool), need * 4))
    artists = dict(db.query(Track.id, Track.artist).filter(Track.id.in_(sample)).all())
    chosen: list[tuple[int, str]] = []
    for track_id in sample:
        artist = artists.get(track_id) or ""
        key = normalize_artist_name(artist)
        if key and key in less_artists:
            continue
        if key and per_artist[key] >= NEIGHBOUR_ARTIST_CAP:
            continue
        if key:
            per_artist[key] += 1
        chosen.append((track_id, artist))
        if len(chosen) >= need:
            break
    return chosen


def next_batch(
    db: Session,
    station: RadioStation,
    user_id: int,
    limit: int = BATCH,
    exclude_track_ids: list[int] | None = None,
) -> tuple[list[tuple[int, str | None]], bool, str | None]:
    """The station's next `limit` tracks as (track_id, reason) pairs,
    whether the library ran thin to make them, and how far the station had
    to reach when it did (None when it did not).

    Raises SeedGone when the seed names nothing in the library any more.
    """
    limit = max(1, min(int(limit or BATCH), 50))
    material = load_material(db, station, user_id)
    if not material.seeds:
        raise SeedGone()

    feedback = station_feedback(db, station)
    less: set[int] = set(feedback["less"])
    less_artists: set[str] = set(feedback["less_artists"])
    extra_seed_ids = [track_id for track_id in feedback["more"] if track_id not in less][:EXTRA_SEEDS]
    extra_seeds = []
    if extra_seed_ids:
        extra_seeds = (
            db.query(Track)
            .options(selectinload(Track.track_genres), selectinload(Track.track_artists))
            .filter(Track.id.in_(extra_seed_ids))
            .all()
        )
    seeds = material.seeds + [track for track in extra_seeds if track.id not in {seed.id for seed in material.seeds}]
    seed_ids = [track.id for track in seeds]
    own_name = material.own_name
    own_share = OWN_SHARE.get(station.seed_type, 4)

    memory = remembered_track_ids(db, station)
    lineup_rows = lineup_of(station)
    handed_out = [int(row["track_id"]) for row in lineup_rows]
    client_excluded = set(int(track_id) for track_id in (exclude_track_ids or []))
    first_batch = not memory and not handed_out and not client_excluded

    own_ids = {track.id for track in material.own}
    material_seed_ids = {track.id for track in material.seeds}
    artist_of: dict[int, str] = {track.id: normalize_artist_name(track.artist or "") for track in material.own}
    for seed in seeds:
        artist_of[seed.id] = normalize_artist_name(seed.artist or "")

    def own_allowed(track_id: int) -> bool:
        # "Less of this artist" reaches the seed's own material too — on a
        # track station the listener may say it of the seed's own artist —
        # but never the seed itself, which is the station.
        return track_id in material_seed_ids or artist_of.get(track_id, "") not in less_artists

    def build(memory_ids: list[int], handed_ids: list[int]):
        excluded = set(memory_ids) | set(handed_ids) | client_excluded | less
        if station.seed_type == "track":
            # The seed itself stays out of the body; a thumbed-up track is
            # a seed for the recommender's sake only and may come round
            # again once the memory lets it.
            excluded |= material_seed_ids
        candidates = _recommend(db, seed_ids, user_id, excluded, CANDIDATE_POOL, refresh=len(lineup_rows))

        chosen_own: list[tuple[int, str | None]] = []
        neighbours: list[tuple[int, str | None]] = []
        seen: set[int] = set()
        per_artist: Counter = Counter()
        for candidate in candidates:
            track_id = candidate["id"]
            if track_id in seen or track_id in excluded:
                continue
            seen.add(track_id)
            if track_id in own_ids:
                if own_allowed(track_id):
                    chosen_own.append((track_id, material.own_label.get(track_id, f"From {own_name}")))
                continue
            key = normalize_artist_name(candidate.get("artist") or "")
            if key and key in less_artists:
                continue
            if key and per_artist[key] >= NEIGHBOUR_ARTIST_CAP:
                continue
            if key:
                per_artist[key] += 1
            artist_of[track_id] = key
            neighbours.append((track_id, _neighbour_reason(candidate, own_name)))
        for track in material.own:
            if track.id in seen or track.id in excluded or not own_allowed(track.id):
                continue
            seen.add(track.id)
            chosen_own.append((track.id, material.own_label.get(track.id, f"From {own_name}")))

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
        # Short of neighbours: the seed's own material fills in, a little
        # past its share; past that the station reaches wider instead.
        own_take = min(len(chosen_own), want - others_take, max(0, own_quota) + OWN_BACKFILL)
        body = _interleave(chosen_own[:own_take], neighbours[:others_take])
        return opener + body, excluded, per_artist

    batch, excluded, per_artist = build(memory, handed_out)
    if len(batch) < limit and (len(memory) > MEMORY_RELAXED or len(handed_out) > MEMORY_RELAXED):
        batch, excluded, per_artist = build(memory[:MEMORY_RELAXED], handed_out[-MEMORY_RELAXED:])

    thin = False
    reach = None
    have = {track_id for track_id, _ in batch}
    if len(batch) < limit:
        thin = True
        seed_families = _families_of(seeds)
        steps = [
            (REACH_GENRE, lambda: _ids_in_families(db, seed_families), f"Shares a genre with {own_name}"),
            (
                REACH_ARTIST,
                lambda: _ids_in_families(db, _families_of(material.own) - seed_families),
                f"Further afield from {own_name}",
            ),
            (REACH_LISTENER, lambda: _ids_in_families(db, _listener_families(db, user_id) - seed_families), "From what you play most"),
            (REACH_LIBRARY, lambda: _library_ids(db), "Somewhere else in your library"),
        ]
        for name, load, reason in steps:
            if len(batch) >= limit:
                break
            picked = _widen(db, load(), excluded | have, less_artists, per_artist, limit - len(batch))
            for track_id, artist in picked:
                batch.append((track_id, reason))
                have.add(track_id)
                artist_of[track_id] = normalize_artist_name(artist)
            if picked:
                reach = name
    if len(batch) < limit:
        # The station has played everything its corner of the library holds.
        # Radio keeps going: the memory is set aside and the pool comes round
        # again, keeping out only what the client is still holding and what
        # the listener said no to.
        keep_out = client_excluded | less | have
        for load in (lambda: _ids_in_families(db, _families_of(seeds)), lambda: _library_ids(db)):
            if len(batch) >= limit:
                break
            picked = _widen(db, load(), keep_out, less_artists, Counter(), limit - len(batch))
            for track_id, artist in picked:
                batch.append((track_id, f"Back around to {own_name}"))
                have.add(track_id)
                keep_out.add(track_id)
                artist_of[track_id] = normalize_artist_name(artist)
            if picked:
                reach = REACH_AGAIN
    return _spread_artists(batch[:limit], artist_of), thin, reach
