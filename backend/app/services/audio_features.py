"""What a track sounds like, as a few dozen numbers.

The map knows who made a track and what people call it; nothing in it says
what the track itself sounds like, so a ballad and a stadium single by the
same artist sit on top of each other. This measures the sound: tempo, how
hard the beat hits, loudness and its variation, brightness (spectral
centroid and rolloff), noisiness (flatness), width (bandwidth), zero
crossings, thirteen MFCC means for timbre and twelve chroma means for
harmony. Three thirty-second excerpts (early, middle, late) are measured and
averaged; on a ten-minute song they agree with the whole track to the
nearest beat at a fifth of the cost.

Audio is decoded by ffmpeg as a subprocess into memory, exactly as the lyrics
engine does it, so librosa's own file readers are never used. librosa is ISC
licensed; its dependency tree is BSD, MIT and Apache apart from two LGPL
components that this module does not call (see docs/audio-analysis.md).

Raw features are stored per track. Standardising them into a unit vector is
a library-wide operation (z-scores need the whole library's spread) and
happens in `standardise_profiles`, called by the map rebuild.
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# librosa compiles its numeric kernels with numba on first use (about
# eighteen seconds on a desktop CPU). Cached in the data volume, that happens
# once per install rather than once per process. Must be set before import.
NUMBA_CACHE_DIR = Path("data/numba_cache")
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE_DIR.resolve()))

SAMPLE_RATE = 22050
EXCERPT_SECONDS = 30.0
# Where in the song the excerpts are taken, as fractions of its length:
# past the intro, the middle, and before the outro.
EXCERPT_POSITIONS = (0.2, 0.5, 0.75)
# Bumped whenever FEATURE_NAMES or the way a feature is measured changes;
# profiles with an older version are measured again.
PROFILE_VERSION = 1

N_MFCC = 13
N_CHROMA = 12
FEATURE_NAMES = (
    "tempo",
    "onset_strength",
    "rms_mean",
    "rms_std",
    "centroid",
    "rolloff",
    "flatness",
    "bandwidth",
    "zcr",
    *(f"mfcc_{i + 1}" for i in range(N_MFCC)),
    *(f"chroma_{i + 1}" for i in range(N_CHROMA)),
)
FEATURE_COUNT = len(FEATURE_NAMES)

# How much of the standardised vector each group of features carries, as a
# share of its squared length. Thirteen MFCC numbers would otherwise
# outweigh tempo thirteen to one.
GROUP_SHARES = {
    "tempo": 0.20,  # log tempo, and the octave-folded circle
    "dynamics": 0.20,  # onset strength, loudness, loudness variation
    "spectral": 0.25,  # centroid, rolloff, flatness, bandwidth, zero crossings
    "timbre": 0.25,  # MFCC
    "harmony": 0.10,  # chroma
}
# Standardised values are clipped here: one bizarre file must not own an axis.
CLIP_SIGMAS = 3.0
# The standardised vector: 3 tempo dims (log tempo, cos, sin) + 3 + 5 + 13 + 12.
SOUND_DIMENSIONS = 3 + 3 + 5 + N_MFCC + N_CHROMA

_available: bool | None = None


def profiler_available() -> bool:
    """Whether librosa imports here. Cached; the answer does not change."""
    global _available
    if _available is None:
        try:
            import librosa  # noqa: F401

            _available = True
        except Exception:  # noqa: BLE001
            _available = False
    return _available


def decode_excerpt(file_path: str, start_seconds: float | None, seconds: float | None) -> np.ndarray:
    """Mono float32 samples at SAMPLE_RATE from ffmpeg, as a pipe: no
    temporary file, no linked decoder."""
    command = ["ffmpeg", "-v", "error", "-nostdin"]
    if start_seconds is not None and start_seconds > 0:
        command += ["-ss", f"{start_seconds:.3f}"]
    if seconds is not None:
        command += ["-t", f"{seconds:.3f}"]
    command += ["-i", file_path, "-vn", "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    result = subprocess.run(command, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "ffmpeg could not decode the file")
    return np.frombuffer(result.stdout, dtype=np.float32)


def probe_duration(file_path: str) -> float | None:
    """The file's length from ffprobe, when the library does not know it."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", file_path],
            capture_output=True,
            timeout=60,
        ).stdout.decode("utf-8", "replace").strip()
        return float(out) if out else None
    except Exception:  # noqa: BLE001
        return None


def features_from_samples(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """The FEATURE_NAMES vector for one excerpt, float32. Pure: numbers in,
    numbers out, so it can be tested on synthetic signals."""
    import librosa

    y = np.asarray(samples, dtype=np.float32)
    if y.size < sample_rate:  # under a second: nothing to measure
        raise ValueError("The excerpt is too short to measure")
    hop = 512
    spectrum = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    onset_env = librosa.onset.onset_strength(S=librosa.power_to_db(spectrum**2, ref=np.max), sr=sample_rate, hop_length=hop)
    tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sample_rate, hop_length=hop)
    tempo_value = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    rms = librosa.feature.rms(S=spectrum)
    mfcc = librosa.feature.mfcc(S=librosa.power_to_db(librosa.feature.melspectrogram(S=spectrum**2, sr=sample_rate)), n_mfcc=N_MFCC)
    chroma = librosa.feature.chroma_stft(S=spectrum, sr=sample_rate)
    values = [
        tempo_value,
        float(onset_env.mean()),
        float(rms.mean()),
        float(rms.std()),
        float(librosa.feature.spectral_centroid(S=spectrum, sr=sample_rate).mean()),
        float(librosa.feature.spectral_rolloff(S=spectrum, sr=sample_rate).mean()),
        float(librosa.feature.spectral_flatness(S=spectrum).mean()),
        float(librosa.feature.spectral_bandwidth(S=spectrum, sr=sample_rate).mean()),
        float(librosa.feature.zero_crossing_rate(y, hop_length=hop).mean()),
        *[float(v) for v in mfcc.mean(axis=1)],
        *[float(v) for v in chroma.mean(axis=1)],
    ]
    out = np.asarray(values, dtype=np.float32)
    if out.shape[0] != FEATURE_COUNT or not np.all(np.isfinite(out)):
        raise ValueError("The measurement came out malformed")
    return out


def combine_excerpts(vectors: list[np.ndarray]) -> np.ndarray:
    """One profile from several excerpts: the median tempo (a beat tracker
    halves or doubles now and then; the middle vote wins), the mean of
    everything else."""
    if not vectors:
        raise ValueError("No excerpts")
    stack = np.stack(vectors).astype(np.float32)
    out = stack.mean(axis=0)
    out[0] = float(np.median(stack[:, 0]))
    return out


def profile_file(file_path: str, duration_seconds: float | None = None) -> np.ndarray:
    """Measure a file: three excerpts when it is long enough, the whole
    thing when it is not. Raises on a file ffmpeg cannot read."""
    duration = float(duration_seconds or 0.0) or probe_duration(file_path) or 0.0
    if duration <= EXCERPT_SECONDS * 1.5:
        samples = decode_excerpt(file_path, None, None)
        return combine_excerpts([features_from_samples(samples)])
    vectors = []
    for fraction in EXCERPT_POSITIONS:
        start = max(0.0, min(duration - EXCERPT_SECONDS, fraction * duration - EXCERPT_SECONDS / 2))
        samples = decode_excerpt(file_path, start, EXCERPT_SECONDS)
        if samples.size >= SAMPLE_RATE:
            vectors.append(features_from_samples(samples))
    if not vectors:
        raise RuntimeError("Nothing decodable in the file")
    return combine_excerpts(vectors)


def pack(features: np.ndarray) -> bytes:
    return np.asarray(features, dtype=np.float32).tobytes()


def unpack(blob: bytes, count: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=count)


def _zscore(column: np.ndarray) -> np.ndarray:
    spread = float(column.std())
    if not math.isfinite(spread) or spread < 1e-9:
        return np.zeros_like(column)
    return np.clip((column - float(column.mean())) / spread, -CLIP_SIGMAS, CLIP_SIGMAS)


def standardise_profiles(features: np.ndarray) -> np.ndarray:
    """Raw profiles (n × FEATURE_COUNT) to unit rows (n × SOUND_DIMENSIONS).

    Tempo is taken on a log scale and also folded by octave onto a circle,
    so 58 and 117 bpm are neighbours (beat trackers disagree by a factor of
    two more than by anything else) while 70 and 140 still differ a little
    on the unfolded axis. Everything else is a clipped z-score over the
    library. Groups are weighted by GROUP_SHARES, then each row is
    normalised, so a dot product between two rows is a cosine.
    """
    raw = np.asarray(features, dtype=np.float32)
    if raw.ndim != 2 or raw.shape[1] != FEATURE_COUNT:
        raise ValueError("Profiles have the wrong width")
    n = raw.shape[0]
    tempo = np.clip(raw[:, 0], 30.0, 300.0)
    log_tempo = np.log2(tempo)
    folded = log_tempo - np.floor(log_tempo)
    angle = 2.0 * np.pi * folded
    tempo_block = np.stack([_zscore(log_tempo), np.cos(angle), np.sin(angle)], axis=1)
    dynamics = np.stack([_zscore(raw[:, i]) for i in (1, 2, 3)], axis=1)
    spectral = np.stack([_zscore(raw[:, i]) for i in (4, 5, 6, 7, 8)], axis=1)
    timbre = np.stack([_zscore(raw[:, 9 + i]) for i in range(N_MFCC)], axis=1)
    harmony = np.stack([_zscore(raw[:, 9 + N_MFCC + i]) for i in range(N_CHROMA)], axis=1)
    blocks = [
        ("tempo", tempo_block),
        ("dynamics", dynamics),
        ("spectral", spectral),
        ("timbre", timbre),
        ("harmony", harmony),
    ]
    out = np.zeros((n, SOUND_DIMENSIONS), dtype=np.float32)
    column = 0
    for name, block in blocks:
        width = block.shape[1]
        # Each group's squared length is its share, whatever its width.
        scale = math.sqrt(GROUP_SHARES[name] / width)
        out[:, column : column + width] = block * scale
        column += width
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (out / norms).astype(np.float32)
