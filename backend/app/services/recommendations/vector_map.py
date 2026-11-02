"""The map: a position for every artist and track, so "near" is a distance.

Radio and the recommender used to know only whether two tracks shared a
genre family — thirteen buckets, the median artist in a bucket of ninety.
This gives each artist a vector built from what the library already holds:

  * its tags, weighted (TF-IDF over the normalised genre tags of its tracks),
  * Last.fm's similar-artist graph, where both ends are in the library,
  * co-listening, aggregated from track co-occurrence to artists,

reduced to a few dozen dimensions with a randomised SVD. Tracks inherit
their credited artists' position, lean a little toward their album, then
move toward the tracks Last.fm and co-listening say they are near. Albums
are the mean of their tracks when asked.

Everything is numpy; no index structure is needed. Nearest neighbours by a
dot product over the whole library is under ten milliseconds at 36k tracks
and stays under a second to several hundred thousand. The matrix lives in
the process cache (36k × 48 float32 ≈ 7 MB) and is rebuilt nightly, after
a scan, and after a Last.fm run. Listening votes do not build the map (see
the report): they steer the query (`VectorIndex.steer`) and, in pass 03,
bend one listener's copy of it.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

import numpy as np
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_cooccurrence import TrackCooccurrence
from app.models.track_genre import TrackGenre
from app.models.track_lastfm_similarity import TrackLastfmSimilarity
from app.models.track_vector import ArtistVector, TrackVector
from app.services.recommendations.genre_utils import is_non_genre_tag, normalize_genre_name
from app.services.recommendations.rec_cache import get_or_build, invalidate
from app.utils.artist_normalization import normalize_artist_name

logger = logging.getLogger(__name__)

# Dimensions kept. Enough to separate thrash from classic rock inside one
# family; few enough that a library of a million tracks is 200 MB.
DIMENSIONS = 48
# Oversampling and power iterations for the randomised SVD: standard
# values, accurate to well past what tag data deserves.
OVERSAMPLE = 16
POWER_ITERATIONS = 2
# Every tag counts — a tag only one artist carries still gives that artist a
# direction of its own, which is right: it is far from everyone. Tags are
# capped by how many artists carry them, so a library with ten thousand
# distinct strings does not make a dense matrix of them.
TAG_MIN_ARTISTS = 1
TAG_MAX = 1500
# A tag row with no weight (the scanner's, or a legacy row) counts as full.
DEFAULT_TAG_WEIGHT = 100.0
# Block weights: tags, the Last.fm artist graph, co-listening.
TAG_BLOCK = 1.0
LASTFM_BLOCK = 1.0
COLISTEN_BLOCK = 0.6
# How a track leaves its artist's position: toward its album, toward what
# Last.fm says is similar, toward what is played around it.
ALBUM_PULL = 0.25
LASTFM_TRACK_PULL = 0.35
COLISTEN_TRACK_PULL = 0.25
INSERT_CHUNK = 5000
CACHE_KEY = "vector_map"
CACHE_TTL_SECONDS = 24 * 60 * 60
EMPTY_TTL_SECONDS = 60
VECTOR_JOB_NAME = "vector_map_rebuild"


# ----------------------------------------------------------------- linear algebra


def _randomized_svd(matvec: Callable, rmatvec: Callable, n_rows: int, n_cols: int, rank: int, seed: int = 7):
    """Top `rank` singular pairs of an n_rows × n_cols matrix given only its
    products, so the sparse blocks never have to be materialised."""
    rng = np.random.default_rng(seed)
    width = max(1, min(rank + OVERSAMPLE, n_rows, n_cols))
    omega = rng.standard_normal((n_cols, width)).astype(np.float32)
    sample = matvec(omega)
    for _ in range(POWER_ITERATIONS):
        q, _ = np.linalg.qr(sample)
        q2, _ = np.linalg.qr(rmatvec(q))
        sample = matvec(q2)
    q, _ = np.linalg.qr(sample)
    small = rmatvec(q).T  # width × n_cols
    u_small, s, _vt = np.linalg.svd(small, full_matrices=False)
    u = q @ u_small
    keep = min(rank, u.shape[1])
    return u[:, :keep], s[:keep]


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


# ------------------------------------------------------------------------ build


@dataclass
class _Edges:
    rows: np.ndarray
    cols: np.ndarray
    vals: np.ndarray

    def apply(self, other: np.ndarray, n_rows: int) -> np.ndarray:
        out = np.zeros((n_rows, other.shape[1]), dtype=np.float32)
        if len(self.rows):
            np.add.at(out, self.rows, self.vals[:, None] * other[self.cols])
        return out


def _symmetric_edges(pairs: dict[tuple[int, int], float], n: int) -> _Edges:
    """Both directions of each pair, plus a self-loop as heavy as the rest of
    the row, each row scaled to sum to one.

    Used as features, a bare adjacency row only resembles rows with the
    *same* neighbours — two artists Last.fm pairs directly would share no
    column at all. The self-loop puts each artist in its own column, so a
    neighbour's row overlaps it there. Rows are normalised so a well-
    connected artist is not louder than a sparsely connected one; artists
    with no edges stay empty and are untouched by this block.
    """
    totals = np.zeros(n, dtype=np.float64)
    rows, cols, vals = [], [], []
    for (a, b), w in pairs.items():
        for r, c in ((a, b), (b, a)):
            rows.append(r)
            cols.append(c)
            vals.append(w)
            totals[r] += w
    if not rows:
        return _Edges(np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32))
    for node in np.nonzero(totals)[0]:
        rows.append(int(node))
        cols.append(int(node))
        vals.append(totals[node])
    totals *= 2.0
    rows_a = np.asarray(rows, dtype=np.int64)
    vals_a = np.asarray(vals, dtype=np.float64) / totals[rows_a]
    return _Edges(rows_a, np.asarray(cols, dtype=np.int64), vals_a.astype(np.float32))


def _track_artist_keys(db: Session) -> dict[int, list[str]]:
    """Credited artists per track, in credit order; the track's artist field
    when there are no credit rows."""
    credits: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for track_id, name, position in db.query(TrackArtist.track_id, TrackArtist.artist_name, TrackArtist.position):
        key = normalize_artist_name(name or "")
        if key:
            credits[track_id].append((position or 0, key))
    out: dict[int, list[str]] = {}
    for track_id, artist in db.query(Track.id, Track.artist):
        keys = [key for _pos, key in sorted(credits.get(track_id, []))]
        if not keys and artist:
            key = normalize_artist_name(artist)
            if key:
                keys = [key]
        seen: list[str] = []
        for key in keys:
            if key not in seen:
                seen.append(key)
        out[track_id] = seen
    return out


def build_artist_vectors(db: Session, dimensions: int = DIMENSIONS) -> tuple[list[str], dict[str, str], np.ndarray, dict]:
    """Artist keys, display names, the (n × k) unit-row matrix, and counts."""
    artist_keys_of = _track_artist_keys(db)
    names: dict[str, str] = {}
    for track_id, artist in db.query(Track.id, Track.artist):
        for key in artist_keys_of.get(track_id, []):
            names.setdefault(key, artist or key)
    for name, in db.query(TrackArtist.artist_name).distinct():
        key = normalize_artist_name(name or "")
        if key and (key not in names or names[key] == key):
            names[key] = name
    artists = sorted(names)
    index = {key: i for i, key in enumerate(artists)}
    n = len(artists)
    if n < 2:
        return artists, names, np.zeros((n, 0), dtype=np.float32), {"artists": n, "tags": 0, "lastfm_pairs": 0, "colisten_pairs": 0}

    # Tags: weight per (artist, tag), from every credited track.
    tag_weight: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for track_id, genre, weight in db.query(TrackGenre.track_id, TrackGenre.genre, TrackGenre.weight):
        if not genre or is_non_genre_tag(genre):
            continue
        tag = normalize_genre_name(genre)
        w = float(weight) if weight is not None else DEFAULT_TAG_WEIGHT
        for key in artist_keys_of.get(track_id, []):
            tag_weight[key][tag] += max(w, 1.0)
    df: dict[str, int] = defaultdict(int)
    for key, tags in tag_weight.items():
        for tag in tags:
            df[tag] += 1
    kept_tags = sorted((tag for tag, count in df.items() if count >= TAG_MIN_ARTISTS), key=lambda t: (-df[t], t))[:TAG_MAX]
    tag_index = {tag: j for j, tag in enumerate(kept_tags)}
    t = len(kept_tags)
    tag_block = np.zeros((n, t), dtype=np.float32)
    for key, tags in tag_weight.items():
        total = sum(tags.values()) or 1.0
        row = index[key]
        for tag, w in tags.items():
            j = tag_index.get(tag)
            if j is not None:
                tag_block[row, j] = (w / total) * math.log(n / df[tag])
    tag_block = _normalize_rows(tag_block) * TAG_BLOCK if t else tag_block

    # Last.fm similar artists, both ends in the library.
    lastfm_pairs: dict[tuple[int, int], float] = {}
    for src, sim, score in db.query(
        ArtistLastfmSimilarity.source_artist_key, ArtistLastfmSimilarity.similar_artist_key, ArtistLastfmSimilarity.match_score
    ):
        a, b = index.get(src), index.get(sim)
        if a is None or b is None or a == b:
            continue
        pair = (min(a, b), max(a, b))
        lastfm_pairs[pair] = max(lastfm_pairs.get(pair, 0.0), float(score or 0.0) or 0.05)
    lastfm_edges = _symmetric_edges(lastfm_pairs, n)

    # Co-listening, tracks folded to artists, log-damped.
    co_pairs: dict[tuple[int, int], float] = defaultdict(float)
    for a_id, b_id, count in db.query(TrackCooccurrence.track_a_id, TrackCooccurrence.track_b_id, TrackCooccurrence.cooccurrence_count):
        for ka in artist_keys_of.get(a_id, [])[:1]:
            for kb in artist_keys_of.get(b_id, [])[:1]:
                a, b = index.get(ka), index.get(kb)
                if a is None or b is None or a == b:
                    continue
                co_pairs[(min(a, b), max(a, b))] += float(count or 0)
    co_edges = _symmetric_edges({pair: math.log1p(w) for pair, w in co_pairs.items()}, n)

    n_cols = t + n + n

    def matvec(omega: np.ndarray) -> np.ndarray:
        out = tag_block @ omega[:t] if t else np.zeros((n, omega.shape[1]), dtype=np.float32)
        out += LASTFM_BLOCK * lastfm_edges.apply(omega[t : t + n], n)
        out += COLISTEN_BLOCK * co_edges.apply(omega[t + n :], n)
        return out

    def rmatvec(q: np.ndarray) -> np.ndarray:
        parts = []
        if t:
            parts.append(tag_block.T @ q)
        parts.append(LASTFM_BLOCK * lastfm_edges.apply(q, n))  # symmetric
        parts.append(COLISTEN_BLOCK * co_edges.apply(q, n))
        return np.vstack(parts)

    rank = max(1, min(dimensions, n, n_cols))
    u, s = _randomized_svd(matvec, rmatvec, n, n_cols, rank)
    embedding = (u * s).astype(np.float32)
    # Artists with no signal at all have zero features and a zero row; they
    # stay zero, which every reader treats as "not on the map".
    signal = np.zeros(n, dtype=bool)
    if t:
        signal |= tag_block.any(axis=1)
    if len(lastfm_edges.rows):
        signal[np.unique(lastfm_edges.rows)] = True
    if len(co_edges.rows):
        signal[np.unique(co_edges.rows)] = True
    embedding[~signal] = 0.0
    embedding = _normalize_rows(embedding)
    counts = {"artists": n, "artists_placed": int(signal.sum()), "tags": t, "lastfm_pairs": len(lastfm_pairs), "colisten_pairs": len(co_pairs)}
    return artists, names, embedding, counts


def build_track_vectors(db: Session, artists: list[str], artist_matrix: np.ndarray) -> tuple[list[int], np.ndarray]:
    """Tracks inherit their artists, lean toward their album, then toward
    their Last.fm and co-listening neighbours. Zero rows are off the map."""
    if artist_matrix.size == 0:
        return [], np.zeros((0, 0), dtype=np.float32)
    k = artist_matrix.shape[1]
    aindex = {key: i for i, key in enumerate(artists)}
    artist_keys_of = _track_artist_keys(db)
    rows = db.query(Track.id, Track.artist, Track.album_artist, Track.album).all()
    track_ids = [row[0] for row in rows]
    tindex = {track_id: i for i, track_id in enumerate(track_ids)}
    m = len(track_ids)
    base = np.zeros((m, k), dtype=np.float32)
    for i, (track_id, _artist, _album_artist, _album) in enumerate(rows):
        keys = [aindex[key] for key in artist_keys_of.get(track_id, []) if key in aindex]
        if keys:
            base[i] = artist_matrix[keys].mean(axis=0)
    placed = base.any(axis=1)

    # Album pull: the mean of the album's placed tracks.
    albums: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, (_track_id, artist, album_artist, album) in enumerate(rows):
        if album:
            albums[((album_artist or artist or "").strip().casefold(), album.strip().casefold())].append(i)
    current = base.copy()
    for members in albums.values():
        if len(members) < 2:
            continue
        idx = np.asarray(members)
        placed_members = idx[placed[idx]]
        if len(placed_members) < 2:
            continue
        mean = base[placed_members].mean(axis=0)
        current[idx] += ALBUM_PULL * mean
    current = _normalize_rows(current)
    current[~current.any(axis=1)] = 0.0

    # Neighbour pull, one step, from the artist-level positions.
    pulls = np.zeros((m, k), dtype=np.float32)
    weights = np.zeros(m, dtype=np.float32)

    def pull(a_id: int, b_id: int, w: float, strength: float) -> None:
        a, b = tindex.get(a_id), tindex.get(b_id)
        if a is None or b is None or a == b or not current[b].any():
            return
        pulls[a] += strength * w * current[b]
        weights[a] += w

    for src, sim, score in db.query(
        TrackLastfmSimilarity.source_track_id, TrackLastfmSimilarity.similar_track_id, TrackLastfmSimilarity.match_score
    ).filter(TrackLastfmSimilarity.similar_track_id.isnot(None)):
        w = float(score or 0.0) or 0.05
        pull(src, sim, w, LASTFM_TRACK_PULL)
        pull(sim, src, w, LASTFM_TRACK_PULL)
    for a_id, b_id, count in db.query(TrackCooccurrence.track_a_id, TrackCooccurrence.track_b_id, TrackCooccurrence.cooccurrence_count):
        w = math.log1p(float(count or 0))
        if w <= 0:
            continue
        pull(a_id, b_id, w, COLISTEN_TRACK_PULL)
        pull(b_id, a_id, w, COLISTEN_TRACK_PULL)
    has_pull = weights > 0
    pulls[has_pull] /= weights[has_pull, None]
    final = current.copy()
    final[has_pull] += pulls[has_pull]
    # A track by an artist off the map still lands where its neighbours are.
    orphan = has_pull & ~current.any(axis=1)
    final[orphan] = pulls[orphan]
    final = _normalize_rows(final)
    final[~final.any(axis=1)] = 0.0
    return track_ids, final


def rebuild_vector_map(db: Session) -> dict:
    """Build and store the whole map. Idempotent; replaces every row."""
    started = datetime.utcnow()
    artists, names, artist_matrix, counts = build_artist_vectors(db)
    track_ids, track_matrix = build_track_vectors(db, artists, artist_matrix)
    dim = int(artist_matrix.shape[1]) if artist_matrix.size else 0

    db.query(TrackVector).delete(synchronize_session=False)
    db.query(ArtistVector).delete(synchronize_session=False)
    artist_rows = [
        {"artist_key": key, "artist_name": names.get(key, key), "vector": artist_matrix[i].tobytes(), "dim": dim, "built_at": started}
        for i, key in enumerate(artists)
        if dim and artist_matrix[i].any()
    ]
    track_rows = [
        {"track_id": track_id, "vector": track_matrix[i].tobytes(), "dim": dim, "built_at": started}
        for i, track_id in enumerate(track_ids)
        if dim and track_matrix[i].any()
    ]
    for start in range(0, len(artist_rows), INSERT_CHUNK):
        db.execute(insert(ArtistVector), artist_rows[start : start + INSERT_CHUNK])
    for start in range(0, len(track_rows), INSERT_CHUNK):
        db.execute(insert(TrackVector), track_rows[start : start + INSERT_CHUNK])
    db.commit()
    invalidate(CACHE_KEY)
    summary = {
        **counts,
        "dimensions": dim,
        "tracks": len(track_ids),
        "tracks_placed": len(track_rows),
        "seconds": round((datetime.utcnow() - started).total_seconds(), 2),
    }
    logger.info("Vector map rebuilt: %s", summary)
    return summary


def rebuild_vector_map_standalone() -> dict:
    """For the scheduler and background hooks — owns its session and a job
    lock, and stands aside while a database migration pauses writes."""
    from app.services import maintenance_mode
    from app.services.job_locking import release_job_lock, try_acquire_job_lock

    if maintenance_mode.writes_paused():
        return {"skipped": "migration_in_progress"}
    db = SessionLocal()
    try:
        if not try_acquire_job_lock(db, VECTOR_JOB_NAME):
            return {"skipped": "already_running"}
        try:
            return rebuild_vector_map(db)
        finally:
            try:
                release_job_lock(db, VECTOR_JOB_NAME)
            except Exception:  # noqa: BLE001
                logger.warning("Could not release the vector map job lock", exc_info=True)
    except Exception:  # noqa: BLE001
        logger.exception("Vector map rebuild failed")
        return {"error": "failed"}
    finally:
        db.close()


def start_vector_rebuild_background() -> None:
    threading.Thread(target=rebuild_vector_map_standalone, name="vector-map-rebuild", daemon=True).start()


def rebuild_vector_map_if_empty() -> None:
    """Self-heal at boot: derived data, so an empty table beside a library
    just means the build never ran."""
    db = SessionLocal()
    try:
        if db.query(TrackVector.track_id).first() is not None:
            return
        if db.query(Track.id).first() is None:
            return
    finally:
        db.close()
    start_vector_rebuild_background()


# ------------------------------------------------------------------------ index


@dataclass
class VectorIndex:
    ids: np.ndarray  # int64, one per placed track
    matrix: np.ndarray  # float32 (n × k), unit rows
    position: dict[int, int]
    artist_keys: list[str]
    artist_matrix: np.ndarray
    artist_position: dict[str, int]
    dim: int
    track_artist: list[str]  # normalised artist key per placed track, aligned with ids
    rows_by_artist: dict[str, np.ndarray] | None = None

    def _rows_of(self, artist_key: str) -> np.ndarray:
        if self.rows_by_artist is None:
            grouped: dict[str, list[int]] = {}
            for row, key in enumerate(self.track_artist):
                if key:
                    grouped.setdefault(key, []).append(row)
            self.rows_by_artist = {key: np.asarray(rows, dtype=np.int64) for key, rows in grouped.items()}
        return self.rows_by_artist.get(artist_key, np.zeros(0, dtype=np.int64))

    def _scores(self, query: np.ndarray, corrections: dict | None = None) -> np.ndarray:
        """Cosine of every placed track to the query, with this listener's
        corrections applied to the artists they cover."""
        scores = self.matrix @ query
        if corrections:
            for artist_key, delta in corrections.items():
                rows = self._rows_of(artist_key)
                if not len(rows):
                    continue
                moved = self.matrix[rows] + delta
                norms = np.linalg.norm(moved, axis=1)
                norms[norms == 0] = 1.0
                scores[rows] = (moved @ query) / norms
        return scores

    def vector_of(self, track_id: int) -> np.ndarray | None:
        row = self.position.get(int(track_id))
        return self.matrix[row] if row is not None else None

    def artist_vector(self, artist_key: str) -> np.ndarray | None:
        row = self.artist_position.get(artist_key)
        return self.artist_matrix[row] if row is not None else None

    def query_from(self, track_ids: Iterable[int]) -> np.ndarray | None:
        """The unit mean of these tracks' positions; None if none is placed."""
        rows = [self.position[int(t)] for t in track_ids if int(t) in self.position]
        if not rows:
            return None
        q = self.matrix[rows].mean(axis=0)
        norm = float(np.linalg.norm(q))
        return (q / norm).astype(np.float32) if norm > 0 else None

    def steer(
        self,
        query: np.ndarray,
        more_ids: Iterable[int] = (),
        less_ids: Iterable[int] = (),
        less_artist_keys: Iterable[str] = (),
        toward: float = 0.5,
        away: float = 0.5,
    ) -> np.ndarray:
        """Relevance feedback: lean the query toward what was thumbed up and
        away from what was thumbed down (tracks and artists)."""
        q = query.astype(np.float32).copy()
        liked = self.query_from(more_ids)
        if liked is not None:
            q += toward * liked
        disliked_rows = [self.position[int(t)] for t in less_ids if int(t) in self.position]
        if disliked_rows:
            q -= away * self.matrix[disliked_rows].mean(axis=0)
        artist_rows = [self.artist_position[k] for k in less_artist_keys if k in self.artist_position]
        if artist_rows:
            q -= away * self.artist_matrix[artist_rows].mean(axis=0)
        norm = float(np.linalg.norm(q))
        return (q / norm).astype(np.float32) if norm > 0 else query

    def nearest(
        self,
        query: np.ndarray,
        limit: int,
        exclude: set[int] | None = None,
        per_artist: int | None = None,
        corrections: dict | None = None,
    ) -> list[tuple[int, float]]:
        """(track_id, cosine) for the `limit` nearest placed tracks, best first.

        `per_artist` caps one artist's share of the answer, so a prolific
        neighbour's hundred tracks do not crowd out the rest of the
        neighbourhood: the answer then spans artists, nearest first.
        """
        if limit <= 0 or not len(self.ids) or query is None:
            return []
        scores = self._scores(query, corrections)
        exclude = exclude or set()
        want = min(len(scores), (limit * 8 if per_artist else limit) + len(exclude))
        if want >= len(scores):
            order = np.argsort(-scores)
        else:
            part = np.argpartition(-scores, want - 1)[:want]
            order = part[np.argsort(-scores[part])]
        out: list[tuple[int, float]] = []
        taken: dict[str, int] = {}
        for row in order:
            track_id = int(self.ids[row])
            if track_id in exclude:
                continue
            if per_artist:
                key = self.track_artist[row]
                if key and taken.get(key, 0) >= per_artist:
                    continue
                if key:
                    taken[key] = taken.get(key, 0) + 1
            out.append((track_id, float(scores[row])))
            if len(out) >= limit:
                break
        return out

    def fit(self, track_ids: Iterable[int], query: np.ndarray, corrections: dict | None = None) -> dict[int, float]:
        """Cosine to the query for whichever of these tracks are placed."""
        wanted = [int(t) for t in track_ids if int(t) in self.position]
        if not wanted or query is None:
            return {}
        rows = np.asarray([self.position[t] for t in wanted])
        if corrections:
            scores = self._scores(query, corrections)[rows]
        else:
            scores = self.matrix[rows] @ query
        return {t: float(s) for t, s in zip(wanted, scores)}


_MISSING = object()


def _load_index(db: Session) -> VectorIndex | None:
    rows = db.query(TrackVector.track_id, TrackVector.vector, TrackVector.dim).all()
    if not rows:
        return None
    dim = int(rows[0][2])
    ids = np.fromiter((row[0] for row in rows), dtype=np.int64, count=len(rows))
    matrix = np.frombuffer(b"".join(row[1] for row in rows), dtype=np.float32).reshape(len(rows), dim)
    artist_by_track = {track_id: normalize_artist_name(artist or "") for track_id, artist in db.query(Track.id, Track.artist)}
    track_artist = [artist_by_track.get(int(track_id), "") for track_id in ids]
    arows = db.query(ArtistVector.artist_key, ArtistVector.vector).all()
    artist_keys = [row[0] for row in arows]
    artist_matrix = (
        np.frombuffer(b"".join(row[1] for row in arows), dtype=np.float32).reshape(len(arows), dim)
        if arows
        else np.zeros((0, dim), dtype=np.float32)
    )
    return VectorIndex(
        ids=ids,
        matrix=matrix,
        position={int(track_id): i for i, track_id in enumerate(ids)},
        artist_keys=artist_keys,
        artist_matrix=artist_matrix,
        artist_position={key: i for i, key in enumerate(artist_keys)},
        dim=dim,
        track_artist=track_artist,
    )


def get_vector_index(db: Session) -> VectorIndex | None:
    """The map, from the process cache; None until the first build has run.
    An empty answer is cached briefly so a boot without a map does not hit
    the table on every request while the self-heal build is running."""
    value = get_or_build(CACHE_KEY, lambda: _load_index(db) or _MISSING, ttl_seconds=CACHE_TTL_SECONDS)
    if value is _MISSING:
        # Re-arm with the short TTL so the next look is soon.
        invalidate(CACHE_KEY)
        get_or_build(CACHE_KEY, lambda: _MISSING, ttl_seconds=EMPTY_TTL_SECONDS)
        return None
    return value


def invalidate_vector_index() -> None:
    invalidate(CACHE_KEY)
