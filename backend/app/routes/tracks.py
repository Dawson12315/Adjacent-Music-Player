from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import mimetypes
import re
import subprocess
import threading
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from jose import JWTError, jwt
from uuid import uuid4

from app.config import settings
from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.album_artwork import AlbumArtwork
from app.models.app_setting import AppSetting
from app.models.artist_artwork import ArtistArtwork
from app.models.listening_event import ListeningEvent
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_cooccurrence import TrackCooccurrence
from app.models.track_genre import TrackGenre
from app.models.track_lastfm_similarity import TrackLastfmSimilarity
from app.models.track_user_stats import TrackUserStats
from app.models.user import User
from app.routes.albums import normalize_album_name
from app.schemas.track import TrackResponse
from app.schemas.track_edit import TrackUpdate
from app.services.auth import get_user_by_id
from app.services.lastfm import scrobble_track, update_now_playing
from app.services.stream_cache_maintenance import clear_stream_caches
from app.services.track_responses import (
    build_single_track_response,
    build_track_response_from_maps,
    build_track_responses,
)
from app.services.metadata_normalizer import normalize_genre_list
from app.services.recommendations.rec_cache import invalidate_library_caches
from app.services.musicbrainz import find_recording_mbid
from app.utils.artist_normalization import normalize_artist_name

logger = logging.getLogger(__name__)

router = APIRouter()

# One hour covers any single listening session for a track; tokens ride in URLs
# (an HLS constraint), so a leaked URL should go stale quickly.
STREAM_TOKEN_EXPIRE_SECONDS = 60 * 60

MAX_TRACKS_BY_IDS = 500

# Ceiling for the legacy no-limit flat listing. Far above any realistic library,
# it exists to bound the worst-case response, not to paginate: clients that can
# paginate should pass `limit`.
MAX_UNPAGED_TRACKS = 50_000

MOBILE_STREAM_PROFILES = {
    "mp3_128": {
        "label": "MP3 128",
        "extension": ".mp3",
        "media_type": "audio/mpeg",
        "cache_version": "v2",
        "ffmpeg_args": [
            "-map", "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata", "-1",
            "-ar", "44100",
            "-ac", "2",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            "-compression_level", "0",
            "-id3v2_version", "3",
            "-write_xing", "1",
            "-f", "mp3",
        ],
    },
    "aac_128": {
        "label": "AAC 128",
        "extension": ".m4a",
        "media_type": "audio/mp4",
        "cache_version": "v1",
        "ffmpeg_args": [
            "-map", "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata", "-1",
            "-af", "aresample=async=1000:min_hard_comp=0.100:first_pts=0",
            "-ar", "44100",
            "-ac", "2",
            "-codec:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-f", "mp4",
        ],
    },
    "mp3_320": {
        "label": "MP3 320",
        "extension": ".mp3",
        "media_type": "audio/mpeg",
        "cache_version": "v7",
        "ffmpeg_args": [
            "-map", "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata", "-1",
            "-ar", "44100",
            "-ac", "2",
            "-codec:a", "libmp3lame",
            "-b:a", "320k",
            "-compression_level", "0",
            "-id3v2_version", "3",
            "-write_xing", "0",
            "-fflags", "+bitexact",
            "-f", "mp3",
        ],
    },
    "aac_256": {
        "label": "AAC 256",
        "extension": ".m4a",
        "media_type": "audio/mp4",
        "cache_version": "v2",
        "ffmpeg_args": [
            "-map", "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-af", "aresample=async=1:first_pts=0",
            "-ar", "44100",
            "-ac", "2",
            "-codec:a", "aac",
            "-b:a", "256k",
            "-movflags", "+faststart",
        ],
    },
    "aac_320": {
        "label": "AAC 320",
        "extension": ".m4a",
        "media_type": "audio/mp4",
        "cache_version": "v2",
        "ffmpeg_args": [
            "-map", "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata", "-1",
            "-af", "aresample=async=1000:min_hard_comp=0.100:first_pts=0",
            "-ar", "44100",
            "-ac", "2",
            "-codec:a", "aac",
            "-b:a", "320k",
            "-movflags", "+faststart",
            "-f", "mp4",
        ],
    },
    "original": {
        "label": "Original",
        "passthrough": True,
    },
}


# Mobile stream cache locking
MOBILE_CACHE_LOCKS: dict[str, threading.Lock] = {}
MOBILE_CACHE_LOCKS_GUARD = threading.Lock()
MOBILE_CACHE_LOCKS_MAX = 512

# ffmpeg is CPU-bound; without a global cap one client asking for many tracks
# spawns one transcode per request and starves the host. Threads queue here.
TRANSCODE_CONCURRENCY = 2
TRANSCODE_SEMAPHORE = threading.BoundedSemaphore(TRANSCODE_CONCURRENCY)

# Every streaming handler is a sync `def`, so it occupies one of the ~40 AnyIO
# worker threads for its whole lifetime. Blocking indefinitely on the
# semaphore therefore converts a CPU queue into a thread-pool outage that
# takes down *every* endpoint, login included. Waiting requests give up after
# this long and return 503 + Retry-After, which players retry natively.
TRANSCODE_WAIT_TIMEOUT_SECONDS = 10

# A single song should transcode in seconds; a hung ffmpeg otherwise holds a
# semaphore slot forever, permanently halving transcode capacity.
FFMPEG_TIMEOUT_SECONDS = 180

# Background pre-build threads are fire-and-forget, so repeated requests for
# the same not-yet-cached variant used to stack one thread per request, all
# queuing on the same semaphore. Membership here means "already being built".
_INFLIGHT_BUILDS: set[str] = set()
_INFLIGHT_GUARD = threading.Lock()


@contextmanager
def transcode_slot(context: str):
    """Hold one transcode slot, or give up rather than pin a worker thread."""
    from app.services.stream_cache_maintenance import has_room_for_transcode

    # The caches share a volume with the database; filling it takes the whole
    # app down, so stop transcoding before that happens. Playback of already
    # cached or passthrough audio is unaffected.
    if not has_room_for_transcode():
        logger.error("Refusing %s: data volume is nearly full", context)
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="The server is out of disk space for audio conversion.",
        )

    acquired = TRANSCODE_SEMAPHORE.acquire(timeout=TRANSCODE_WAIT_TIMEOUT_SECONDS)

    if not acquired:
        logger.warning("Transcode queue full; refusing %s", context)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The server is busy preparing audio. Try again in a moment.",
            headers={"Retry-After": "5"},
        )

    try:
        yield
    finally:
        TRANSCODE_SEMAPHORE.release()


@contextmanager
def inflight_build(key: str):
    """Yield True when this caller owns the build, False if one is running."""
    with _INFLIGHT_GUARD:
        if key in _INFLIGHT_BUILDS:
            yield False
            return

        _INFLIGHT_BUILDS.add(key)

    try:
        yield True
    finally:
        with _INFLIGHT_GUARD:
            _INFLIGHT_BUILDS.discard(key)

# HLS streaming constants
HLS_SEGMENT_DURATION_SECONDS = 4
HLS_CACHE_ROOT = Path("data/hls_cache")
# Matches ffmpeg's -hls_segment_filename output plus the playlist itself.
HLS_SEGMENT_NAME_PATTERN = re.compile(r"segment_\d{5}\.ts|index\.m3u8")
HLS_STARTUP_QUALITY = "aac_320"
HLS_DEFAULT_QUALITY = "aac_320"

# The advertised ABR ladder.
#
# ffmpeg's native `aac` encoder saturates around 224 kbps for 44.1 kHz stereo —
# measured on deliberately incompressible input, `-b:a 256k` and `-b:a 320k`
# both land at ~221 kbps — and the runtime image has no libfdk_aac to do
# better. So `aac_256` and `aac_320` were two rungs carrying the same bytes:
# the player could "adapt" between identical streams, and every track paid for
# two transcodes and two cache entries to make that possible. Only aac_320 is
# advertised now.
#
# BANDWIDTH is what a player budgets against, so these are measured off real
# segments rather than copied from the bitrate we ask ffmpeg for. Both numbers
# sit above the audio bitrate because MPEG-TS packetisation adds roughly 10%:
# aac_320 audio lands at ~223 kbps and its segments at ~244, aac_128 at ~130
# and ~142. The old list declared 320000 for the top rung, which made players
# on a ~250 kbps link step down to a variant that was not actually smaller.
HLS_QUALITY_VARIANTS = [
    {"quality": "aac_320", "bandwidth": 256000, "name": "AAC High", "codecs": "mp4a.40.2"},
    {"quality": "aac_128", "bandwidth": 152000, "name": "AAC 128", "codecs": "mp4a.40.2"},
]

# What an HLS request is allowed to *name*, which is broader than what we
# advertise: app builds already in the field ask for `aac_256` by name, and
# rejecting them would turn a cosmetic ladder change into silence on someone
# else's phone. It still resolves to a real profile — the same one aac_320
# uses in all but name.
HLS_ACCEPTED_QUALITIES = {variant["quality"] for variant in HLS_QUALITY_VARIANTS} | {
    "aac_256",
}

# Preferences an HLS ladder cannot express, mapped to the rung that comes
# closest. MP3 320 is a container choice rather than a quality one — it exists
# for car stereos that will not read AAC — so it maps to the top rung, not to
# Data Saver.
HLS_QUALITY_SUBSTITUTIONS = {
    "mp3_128": "aac_128",
    "mp3_320": "aac_320",
}


def get_mobile_cache_lock(cache_key: str) -> threading.Lock:
    with MOBILE_CACHE_LOCKS_GUARD:
        lock = MOBILE_CACHE_LOCKS.get(cache_key)

        if lock is None:
            # One lock per (track, quality) accumulates forever on a large
            # library; drop idle ones once the table gets big.
            if len(MOBILE_CACHE_LOCKS) >= MOBILE_CACHE_LOCKS_MAX:
                for key in [k for k, v in MOBILE_CACHE_LOCKS.items() if not v.locked()]:
                    del MOBILE_CACHE_LOCKS[key]

            lock = threading.Lock()
            MOBILE_CACHE_LOCKS[cache_key] = lock

        return lock


def source_fingerprint(file_path: Path) -> str:
    """Identity of the *audio content* a cache entry was made from.

    Cache entries used to be keyed by track id alone and validated by mtime
    comparison. Track ids are reassigned by purge + rescan, and library files
    are usually older than the cache — so a stale entry for old track N would
    pass validation and play the wrong song for new track N. Binding entries
    to (path, mtime, size) makes that structurally impossible: different
    audio always means a different cache name.
    """
    stat = file_path.stat()
    raw = f"{file_path}:{stat.st_mtime_ns}:{stat.st_size}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# HLS cache path helper
def get_hls_cache_paths(track_id: int, quality: str, fingerprint: str):
    track_dir = HLS_CACHE_ROOT / f"track_{track_id}_{fingerprint}" / quality
    playlist_path = track_dir / "index.m3u8"
    segment_pattern = track_dir / "segment_%05d.ts"

    return {
        "track_dir": track_dir,
        "playlist_path": playlist_path,
        "segment_pattern": segment_pattern,
    }


def get_hls_ffmpeg_args(profile: dict) -> list[str]:
    args = list(profile.get("ffmpeg_args", []))
    cleaned_args = []
    index = 0

    while index < len(args):
        current_arg = args[index]

        if current_arg == "-f" and index + 1 < len(args):
            index += 2
            continue

        if current_arg == "-movflags" and index + 1 < len(args):
            index += 2
            continue

        if current_arg in {"-id3v2_version", "-write_xing"} and index + 1 < len(args):
            index += 2
            continue

        cleaned_args.append(current_arg)
        index += 1

    return cleaned_args


def iter_file_range(file_path: Path, start: int, end: int, chunk_size: int = 256 * 1024):
    with file_path.open("rb") as file:
        file.seek(start)
        remaining = end - start + 1

        while remaining > 0:
            chunk = file.read(min(chunk_size, remaining))

            if not chunk:
                break

            remaining -= len(chunk)
            yield chunk


def range_file_response(
    request: Request,
    file_path: Path,
    media_type: str,
    filename: str,
    cache_seconds: int = 86400,
):
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    base_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": f"public, max-age={cache_seconds}, no-transform",
        "Content-Disposition": f'inline; filename="{filename}"',
    }

    if not range_header:
        headers = {
            **base_headers,
            "Content-Length": str(file_size),
        }

        return StreamingResponse(
            iter_file_range(file_path, 0, file_size - 1),
            media_type=media_type,
            headers=headers,
            status_code=200,
        )

    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid range header")

    range_value = range_header.replace("bytes=", "", 1).strip()
    start_text, _, end_text = range_value.partition("-")

    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        else:
            suffix_length = int(end_text)
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError:
        raise HTTPException(status_code=416, detail="Invalid range header")

    if start < 0 or end >= file_size or start > end:
        return StreamingResponse(
            iter(()),
            status_code=416,
            headers={
                **base_headers,
                "Content-Range": f"bytes */{file_size}",
            },
        )

    content_length = end - start + 1
    headers = {
        **base_headers,
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(content_length),
    }

    return StreamingResponse(
        iter_file_range(file_path, start, end),
        media_type=media_type,
        headers=headers,
        status_code=206,
    )



# Helper: ensure mobile stream cache
def ensure_mobile_stream_cache(
    track: Track,
    file_path: Path,
    profile: dict,
    quality: str,
) -> Path:
    cache_dir = Path("data/mobile_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    output_extension = profile["extension"]
    cache_version = profile.get("cache_version", "v1")
    fingerprint = source_fingerprint(file_path)
    cache_basename = f"track_{track.id}_{fingerprint}_{quality}_{cache_version}"
    cached_file_path = cache_dir / f"{cache_basename}{output_extension}"
    temp_file_path = cache_dir / f"{cache_basename}_{uuid4().hex}.tmp{output_extension}"

    # The fingerprint in the name carries source identity (path+mtime+size),
    # so existence is validity — no mtime comparison to get wrong.
    def is_cache_valid() -> bool:
        return cached_file_path.exists() and cached_file_path.stat().st_size > 0

    if is_cache_valid():
        return cached_file_path

    cache_key = f"{track.id}:{quality}:{cache_version}"
    cache_lock = get_mobile_cache_lock(cache_key)

    with cache_lock:
        if is_cache_valid():
            return cached_file_path

        if temp_file_path.exists():
            temp_file_path.unlink()

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(file_path),
            *profile["ffmpeg_args"],
            str(temp_file_path),
        ]

        logger.info("Transcoding track %s (%s) for mobile cache", track.id, quality)

        with transcode_slot(f"mobile transcode of track {track.id} ({quality})"):
            try:
                result = subprocess.run(
                    ffmpeg_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=FFMPEG_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                if temp_file_path.exists():
                    temp_file_path.unlink()

                logger.error(
                    "ffmpeg timed out transcoding track %s (%s)", track.id, quality
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Audio conversion timed out.",
                )

        if result.returncode != 0:
            if temp_file_path.exists():
                temp_file_path.unlink()

            # ffmpeg stderr contains absolute library paths; log it, don't return it.
            logger.error(
                "Mobile transcode failed for track %s (%s): %s",
                track.id,
                quality,
                result.stderr.strip(),
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create mobile stream",
            )

        if temp_file_path.exists():
            temp_file_path.replace(cached_file_path)
        elif not cached_file_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Mobile stream cache file was not created",
            )

    return cached_file_path


# HLS streaming cache helper
def ensure_hls_stream_cache(
    track: Track,
    file_path: Path,
    profile: dict,
    quality: str,
):
    if profile.get("passthrough"):
        raise HTTPException(
            status_code=400,
            detail="Original quality is not supported for HLS streaming",
        )

    cache_version = profile.get("cache_version", "v1")
    fingerprint = source_fingerprint(file_path)
    cache_key = f"hls:{track.id}:{fingerprint}:{quality}:{cache_version}"
    cache_lock = get_mobile_cache_lock(cache_key)

    paths = get_hls_cache_paths(track.id, quality, fingerprint)
    track_dir = paths["track_dir"]
    playlist_path = paths["playlist_path"]
    segment_pattern = paths["segment_pattern"]

    # Source identity lives in the directory name; existence is validity.
    def is_cache_valid() -> bool:
        return playlist_path.exists() and playlist_path.stat().st_size > 0

    if is_cache_valid():
        return playlist_path

    with cache_lock:
        if is_cache_valid():
            return playlist_path

        if track_dir.exists():
            shutil.rmtree(track_dir, ignore_errors=True)

        track_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(file_path),
            *get_hls_ffmpeg_args(profile),
            "-f",
            "hls",
            "-hls_time",
            str(HLS_SEGMENT_DURATION_SECONDS),
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(segment_pattern),
            str(playlist_path),
        ]

        logger.info("Generating HLS stream for track %s (%s)", track.id, quality)

        with transcode_slot(f"HLS build of track {track.id} ({quality})"):
            try:
                result = subprocess.run(
                    ffmpeg_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=FFMPEG_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                shutil.rmtree(track_dir, ignore_errors=True)

                logger.error(
                    "ffmpeg timed out building HLS for track %s (%s)",
                    track.id,
                    quality,
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Audio conversion timed out.",
                )

        if result.returncode != 0:
            shutil.rmtree(track_dir, ignore_errors=True)

            # ffmpeg stderr contains absolute library paths; log it, don't return it.
            logger.error(
                "HLS generation failed for track %s (%s): %s",
                track.id,
                quality,
                result.stderr.strip(),
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create HLS stream",
            )

        if not playlist_path.exists():
            raise HTTPException(
                status_code=500,
                detail="HLS playlist generation failed",
            )

    return playlist_path


# --- HLS helper functions ---

def build_hls_variant_playlist_url(
    track_id: int,
    quality: str,
    token: str,
    fast_start_only: bool = False,
) -> str:
    fast_start_param = "&fast_start=1" if fast_start_only else ""
    return f"/api/tracks/{track_id}/hls/{quality}/index.m3u8?token={token}{fast_start_param}"


def get_requested_hls_quality(request: Request) -> str:
    requested_quality = request.query_params.get("quality") or HLS_DEFAULT_QUALITY

    # An HLS ladder is AAC-only, but a client's *preference* need not be. Map
    # the MP3 tiers onto their nearest AAC rung rather than refusing them.
    #
    # This used to 400 on anything outside the ladder, which meant a phone with
    # "MP3 320 kbps" selected played nothing at all the moment it left Wi-Fi.
    # Newer builds resolve the substitution before they ask, but builds already
    # installed do not, and they are the ones this protects.
    requested_quality = HLS_QUALITY_SUBSTITUTIONS.get(
        requested_quality, requested_quality
    )

    profile = MOBILE_STREAM_PROFILES.get(requested_quality)

    if not profile or profile.get("passthrough"):
        raise HTTPException(status_code=400, detail="Invalid HLS quality")

    if requested_quality not in HLS_ACCEPTED_QUALITIES:
        raise HTTPException(status_code=400, detail="Invalid HLS quality")

    return requested_quality


def prepare_hls_variants_in_background(track_id: int, file_path_text: str):
    file_path = Path(file_path_text)

    if not file_path.exists():
        return

    # Callers fire-and-forget one thread per request. Repeated requests for a
    # track whose variants are still building used to stack threads that all
    # queued on the transcode semaphore; one build per track is enough.
    with inflight_build(f"hls:{track_id}") as owner:
        if not owner:
            logger.debug("HLS variants for track %s already building", track_id)
            return

        track_stub = Track(id=track_id, file_path=file_path_text)

        for variant in HLS_QUALITY_VARIANTS:
            quality = variant["quality"]

            if quality == HLS_STARTUP_QUALITY:
                continue

            profile = MOBILE_STREAM_PROFILES.get(quality)

            if not profile or profile.get("passthrough"):
                continue

            try:
                ensure_hls_stream_cache(
                    track=track_stub,
                    file_path=file_path,
                    profile=profile,
                    quality=quality,
                )
            except HTTPException:
                # Transcode queue was full (503) or ffmpeg timed out — this is
                # opportunistic pre-building, so drop it and let the next
                # on-demand request rebuild.
                logger.info(
                    "Skipped background HLS variant for track %s (%s): busy",
                    track_id,
                    quality,
                )
            except Exception:
                logger.exception(
                    "Background HLS generation failed for track %s (%s)",
                    track_id,
                    quality,
                )


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


def get_stream_token(request: Request) -> str | None:
    """Prefer header transport; keep the query param for HLS playlist URLs.

    Playlist rewriting has to embed the token in segment URLs (media players
    fetch them without custom headers), but clients that can set headers should
    keep tokens out of URLs, logs, and referrers.
    """
    header_token = request.headers.get("x-stream-token")
    if header_token:
        return header_token

    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return request.query_params.get("token")


def verify_stream_token(token: str, track_id: int, db: Session) -> bool:
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

    # A token must not outlive its user: deactivating an account revokes
    # streaming immediately instead of at token expiry.
    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        return False

    user = get_user_by_id(db, user_id)

    return bool(user and user.is_active)


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
    """Single-track wrapper over the shared batched builder. List endpoints
    should call build_track_responses() so artwork resolves in two queries
    total instead of two per track."""
    if db is None:
        return build_track_response_from_maps(track, {}, {})

    return build_single_track_response(db, track)


def build_track_responses_for_ids(track_ids: list[int], db: Session) -> list[TrackResponse]:
    if not track_ids:
        return []

    tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_artists),
            selectinload(Track.track_genres),
        )
        .filter(Track.id.in_(track_ids))
        .all()
    )

    track_by_id = {track.id: track for track in tracks}
    ordered_tracks = [
        track_by_id[track_id] for track_id in track_ids if track_id in track_by_id
    ]

    return build_track_responses(db, ordered_tracks)


@router.get("/tracks/count", tags=["tracks"])
def get_track_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(func.count(Track.id)).scalar()
    return {"count": count}


@router.get("/tracks", tags=["tracks"])
def list_tracks(
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    sort_by: str = Query("artist", pattern="^(title|album|artist)$"),
    section: str | None = Query(None, pattern="^(\\$#|[A-Za-z])$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Track).options(
        selectinload(Track.track_artists),
        selectinload(Track.track_genres),
    )

    cleaned_search = search.strip() if search else ""

    if cleaned_search:
        pattern = f"%{cleaned_search.lower()}%"
        query = query.filter(
            func.lower(Track.title).like(pattern)
            | func.lower(Track.artist).like(pattern)
            | func.lower(Track.album).like(pattern)
            | func.lower(Track.genre).like(pattern)
        )

    total = query.count()

    sort_columns = {
        "title": [
            func.lower(Track.title),
            func.lower(Track.artist),
            func.lower(Track.album),
            Track.id,
        ],
        "album": [
            func.lower(Track.album),
            func.lower(Track.artist),
            func.lower(Track.title),
            Track.id,
        ],
        "artist": [
            func.lower(Track.artist),
            func.lower(Track.album),
            func.lower(Track.title),
            Track.id,
        ],
    }

    query = query.order_by(*sort_columns.get(sort_by, sort_columns["artist"]))

    if section:
        sort_field = {
            "title": Track.title,
            "album": Track.album,
            "artist": Track.artist,
        }.get(sort_by, Track.artist)
    
        sort_value = func.lower(func.coalesce(sort_field, ""))
        normalized_section = section.lower()
    
        if normalized_section == "$#":
            offset = 0
        else:
            offset = query.filter(sort_value < normalized_section).count()
    
    if limit is not None:
        query = query.offset(offset).limit(limit)
    else:
        # Legacy flat listing (used by clients that load the whole library).
        # Bounded so a single request can never build an arbitrarily large
        # response; real libraries sit far below this.
        query = query.limit(MAX_UNPAGED_TRACKS)

    tracks = query.all()

    items = build_track_responses(db, tracks)

    if limit is None:
        return items

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


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



# Endpoint: Prepare mobile stream cache
@router.post("/tracks/{track_id}/mobile-stream-cache/prepare", tags=["tracks"])
def prepare_mobile_stream_cache(
    track_id: int,
    quality: str = Query("mp3_320"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = MOBILE_STREAM_PROFILES.get(quality)

    if not profile:
        raise HTTPException(status_code=400, detail="Invalid mobile stream quality")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if profile.get("passthrough"):
        return {"prepared": True, "passthrough": True}
    else:
        cached_file_path = ensure_mobile_stream_cache(
            track=track,
            file_path=file_path,
            profile=profile,
            quality=quality,
        )

    return {
        "prepared": True,
        "track_id": track.id,
        "quality": quality,
        "size_bytes": cached_file_path.stat().st_size,
    }


# Endpoint: Mobile stream

@router.get("/tracks/{track_id}/mobile-stream", tags=["tracks"])
def mobile_stream_track(
    track_id: int,
    request: Request,
    quality: str = Query("mp3_320"),
    db: Session = Depends(get_db),
):
    token = get_stream_token(request)

    if not token or not verify_stream_token(token, track_id, db):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    profile = MOBILE_STREAM_PROFILES.get(quality)

    if not profile:
        raise HTTPException(status_code=400, detail="Invalid mobile stream quality")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    source_extension = file_path.suffix.lower()

    if profile.get("passthrough"):
        media_type, _ = mimetypes.guess_type(str(file_path))
    
        return range_file_response(
            request=request,
            file_path=file_path,
            media_type=media_type or "application/octet-stream",
            filename=f"track-{track.id}{source_extension}",
        )

    output_extension = profile["extension"]
    cached_file_path = ensure_mobile_stream_cache(
        track=track,
        file_path=file_path,
        profile=profile,
        quality=quality,
    )

    return range_file_response(
        request=request,
        file_path=cached_file_path,
        media_type=profile["media_type"],
        filename=f"track-{track.id}{output_extension}",
    )


# HLS streaming endpoints

@router.get("/tracks/{track_id}/hls/master.m3u8", tags=["tracks"])
def get_hls_master_playlist(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    token = get_stream_token(request)
    fast_start_only = request.query_params.get("fast_start") == "1"
    requested_hls_quality = get_requested_hls_quality(request)

    if not token or not verify_stream_token(token, track_id, db):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    startup_profile = MOBILE_STREAM_PROFILES.get(requested_hls_quality)

    if not startup_profile or startup_profile.get("passthrough"):
        raise HTTPException(status_code=500, detail="Invalid HLS startup quality")

    ensure_hls_stream_cache(
        track=track,
        file_path=file_path,
        profile=startup_profile,
        quality=requested_hls_quality,
    )

    if not fast_start_only:
        threading.Thread(
            target=prepare_hls_variants_in_background,
            args=(track.id, str(file_path)),
            daemon=True,
        ).start()

    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

    # A real master playlist: every variant is listed so ABR-capable players
    # can actually adapt (the old master carried only the requested quality,
    # which made the master/variant indirection decorative). The requested
    # quality goes first — players start with the first variant, so an
    # explicit quality choice still lands before adaptation kicks in.
    ordered_variants = sorted(
        HLS_QUALITY_VARIANTS,
        key=lambda variant: variant["quality"] != requested_hls_quality,
    )

    for variant in ordered_variants:
        quality = variant["quality"]
        profile = MOBILE_STREAM_PROFILES.get(quality)

        if not profile or profile.get("passthrough"):
            continue

        lines.append(
            f'#EXT-X-STREAM-INF:BANDWIDTH={variant["bandwidth"]},NAME="{variant["name"]}",CODECS="{variant["codecs"]}"'
        )
        lines.append(
            build_hls_variant_playlist_url(track.id, quality, token, fast_start_only)
        )

    return Response(
        content="\n".join(lines) + "\n",
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.get("/tracks/{track_id}/hls/{quality}/index.m3u8", tags=["tracks"])
def get_hls_quality_playlist(
    track_id: int,
    quality: str,
    request: Request,
    db: Session = Depends(get_db),
):
    token = get_stream_token(request)
    fast_start_only = request.query_params.get("fast_start") == "1"

    if not token or not verify_stream_token(token, track_id, db):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    profile = MOBILE_STREAM_PROFILES.get(quality)

    if not profile or profile.get("passthrough"):
        raise HTTPException(status_code=400, detail="Invalid HLS quality")

    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    playlist_path = ensure_hls_stream_cache(
        track=track,
        file_path=file_path,
        profile=profile,
        quality=quality,
    )

    if quality == HLS_DEFAULT_QUALITY and not fast_start_only:
        threading.Thread(
            target=prepare_hls_variants_in_background,
            args=(track.id, str(file_path)),
            daemon=True,
        ).start()

    playlist_text = playlist_path.read_text()
    rewritten_lines = []

    for line in playlist_text.splitlines():
        stripped = line.strip()

        if stripped and not stripped.startswith("#"):
            segment_name = Path(stripped).name
            rewritten_lines.append(
                f"/api/tracks/{track.id}/hls/{quality}/{segment_name}?token={token}"
                + ("&fast_start=1" if fast_start_only else "")
            )
        else:
            rewritten_lines.append(line)

    return Response(
        content="\n".join(rewritten_lines) + "\n",
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "public, max-age=60"},
    )




@router.get("/tracks/{track_id}/hls/{quality}/{segment_name}", tags=["tracks"])
def get_hls_segment(
    track_id: int,
    quality: str,
    segment_name: str,
    request: Request,
    db: Session = Depends(get_db),
):
    token = get_stream_token(request)

    if not token or not verify_stream_token(token, track_id, db):
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    # Both values become path components; only ffmpeg-generated names are valid.
    profile = MOBILE_STREAM_PROFILES.get(quality)
    if not profile or profile.get("passthrough"):
        raise HTTPException(status_code=400, detail="Invalid HLS quality")

    if not HLS_SEGMENT_NAME_PATTERN.fullmatch(segment_name):
        raise HTTPException(status_code=404, detail="HLS segment not found")

    # The cache directory embeds the source fingerprint, so the track's file
    # identity is needed to locate segments.
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    segment_path = (
        get_hls_cache_paths(track_id, quality, source_fingerprint(file_path))["track_dir"]
        / segment_name
    )

    if not segment_path.exists():
        raise HTTPException(status_code=404, detail="HLS segment not found")

    return FileResponse(
        path=segment_path,
        media_type="video/mp2t",
        filename=segment_name,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post("/tracks/{track_id}/hls/prepare", tags=["tracks"])
def prepare_hls_stream(
    track_id: int,
    quality: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track = db.query(Track).filter(Track.id == track_id).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    file_path = Path(track.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    requested_qualities = (
        [variant["quality"] for variant in HLS_QUALITY_VARIANTS]
        if quality == "all"
        else [quality]
    )

    requested_qualities = [
        HLS_QUALITY_SUBSTITUTIONS.get(requested_quality, requested_quality)
        for requested_quality in requested_qualities
    ]

    prepared = []

    for requested_quality in requested_qualities:
        profile = MOBILE_STREAM_PROFILES.get(requested_quality)

        if not profile or profile.get("passthrough"):
            raise HTTPException(status_code=400, detail="Invalid HLS quality")

        playlist_path = ensure_hls_stream_cache(
            track=track,
            file_path=file_path,
            profile=profile,
            quality=requested_quality,
        )

        prepared.append(
            {
                "quality": requested_quality,
                "playlist": str(playlist_path),
            }
        )
    if quality != "all":
        threading.Thread(
            target=prepare_hls_variants_in_background,
            args=(track.id, str(file_path)),
            daemon=True,
        ).start()
    return {
        "prepared": True,
        "track_id": track.id,
        "qualities": prepared,
    }

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

    # Every table referencing tracks is cleared explicitly, in bulk statements
    # that execute immediately (per-object ORM assignments sat unflushed in
    # this autoflush=False session and tripped FKs). Explicit ordering matters
    # for another reason too: whether a table's FK carries ON DELETE CASCADE
    # depends on which schema vintage created it, so cascades cannot be
    # trusted on databases that predate the current migrations.
    db.query(PlaylistTrack).delete()
    db.query(PlaybackQueueItem).delete()

    db.query(PlaybackSession).update(
        {
            PlaybackSession.current_track_id: None,
            PlaybackSession.queue_index: -1,
            PlaybackSession.current_time_seconds: 0,
            PlaybackSession.is_playing: False,
        },
        synchronize_session=False,
    )

    db.query(TrackLastfmSimilarity).delete()
    db.query(TrackCooccurrence).delete()
    db.query(TrackUserStats).delete()
    db.query(ListeningEvent).delete()
    db.query(TrackArtist).delete()
    db.query(TrackGenre).delete()
    db.query(Track).delete()

    db.commit()
    invalidate_library_caches()

    # The transcode caches are derived from the tracks that no longer exist;
    # dropping them reclaims disk and removes any chance of an old entry
    # shadowing a future track (ids restart after a purge).
    clear_stream_caches()

    return {
        "message": "All stored tracks purged",
        "deleted_count": deleted_tracks,
    }


@router.get("/tracks/by-ids", response_model=list[TrackResponse], tags=["tracks"])
def get_tracks_by_ids(
    ids: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    track_ids = []

    for raw_track_id in ids.split(","):
        cleaned_track_id = raw_track_id.strip()

        if not cleaned_track_id:
            continue

        try:
            track_ids.append(int(cleaned_track_id))
        except ValueError:
            continue

        if len(track_ids) >= MAX_TRACKS_BY_IDS:
            break

    return build_track_responses_for_ids(track_ids, db)


@router.get("/tracks/{track_id}", response_model=TrackResponse, tags=["tracks"])
def get_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    return build_track_response(track, db)


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