"""What the audio says about a track, as three flags the radio respects.

* `vocal_state`: "vocal" when there are sung words, "instrumental" when
  there are none, null when nobody has listened yet.
* `language`: the language of the vocals (ISO 639-1), with a confidence.
  Only ever set on a vocal track: Whisper answers with *some* language for
  a guitar solo, and that answer means nothing.
* `explicit_state`: "explicit" when the lyrics carry words a listener may
  not want a child to hear, "clean" when they do not, null without words.

Flags come two ways. The lyrics engine's full pass sets them for free as a
by-product of producing words. For everything else, `detect` listens to one
thirty-second window (two for a track that sounds instrumental) with the
same Whisper model: the language from the encoder, the words from a greedy
decode. That is ten times cheaper than transcribing the song.

An admin can set any flag by hand; the server then leaves that track alone
(`flags_set_by == "admin"`). Every flag is a machine's guess otherwise and
the clients say "detected".
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.models.track import Track
from app.services import lyrics_engine

logger = logging.getLogger(__name__)

VOCAL = "vocal"
INSTRUMENTAL = "instrumental"
EXPLICIT = "explicit"
CLEAN = "clean"
SET_BY_DETECTED = "detected"
SET_BY_ADMIN = "admin"
VOCAL_STATES = (VOCAL, INSTRUMENTAL)
EXPLICIT_STATES = (EXPLICIT, CLEAN)

# Whisper's language guess is kept only when it is at least this sure.
LANGUAGE_MIN_CONFIDENCE = 0.5
WINDOW_SECONDS = 30.0
# Where to listen: past the intro, then later if the first window was quiet.
WINDOW_POSITIONS = (0.4, 0.65)
# Words heard in one window: at least this many, and at least this many
# *different* ones, says "vocal". A window with at most MAX_WORDS_INSTRUMENTAL
# says nothing; when no window says more the track is "instrumental". In
# between it stays unknown rather than wrong. Windows are judged one at a
# time: Whisper hallucinates a word or two on a pure tone, and those must
# not add up across windows into a song.
MIN_WORDS_VOCAL = 6
MIN_DISTINCT_WORDS_VOCAL = 4
MAX_WORDS_INSTRUMENTAL = 2
# A segment counts only when the model was reasonably sure of it. Measured
# on tones: hallucinated segments sit at an average log-probability near -2
# with a one-word text; sung lines sit above -1 (see docs/audio-analysis.md).
SEGMENT_MIN_LOGPROB = -1.0
SEGMENT_MAX_COMPRESSION = 2.4

# Words that make lyrics explicit. Matched on word boundaries with the
# usual endings; a short, deliberately coarse list — the aim is a clean
# switch that errs toward "explicit", with an admin override behind it.
EXPLICIT_WORDS = (
    "fuck",
    "fucking",
    "fucked",
    "fucker",
    "fuckers",
    "motherfucker",
    "motherfuckers",
    "motherfucking",
    "shit",
    "shitty",
    "bullshit",
    "bitch",
    "bitches",
    "asshole",
    "assholes",
    "dick",
    "dicks",
    "cock",
    "cocks",
    "pussy",
    "cunt",
    "cunts",
    "whore",
    "whores",
    "slut",
    "sluts",
    "nigga",
    "niggas",
    "nigger",
    "niggers",
    "faggot",
    "faggots",
    # Spanish
    "puta",
    "putas",
    "puto",
    "putos",
    "mierda",
    "joder",
    "coño",
    "cabrón",
    "cabron",
    "cabrones",
    "pendejo",
    "pendejos",
    "chingar",
    "chinga",
    "chingada",
    "verga",
)
_EXPLICIT_PATTERN = re.compile(r"\b(" + "|".join(re.escape(word) for word in EXPLICIT_WORDS) + r")\b", re.IGNORECASE)


def flags_available() -> bool:
    """Detection needs the speech model the lyrics engine uses."""
    return lyrics_engine.transcriber_available()


def explicit_from_text(plain: str | None) -> str | None:
    """"explicit" or "clean" for a lyrics text; None for no text."""
    if not plain or not plain.strip():
        return None
    return EXPLICIT if _EXPLICIT_PATTERN.search(plain) else CLEAN


def _decode_window(file_path: str, start_seconds: float, seconds: float) -> np.ndarray:
    command = [
        "ffmpeg", "-v", "error", "-nostdin",
        "-ss", f"{max(0.0, start_seconds):.3f}", "-t", f"{seconds:.3f}",
        "-i", file_path, "-vn", "-f", "f32le", "-ac", "1", "-ar", "16000", "-",
    ]
    result = subprocess.run(command, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "ffmpeg could not decode the file")
    return np.frombuffer(result.stdout, dtype=np.float32)


def _count_words(model, audio: np.ndarray) -> tuple[int, int]:
    """(words, distinct words) the model is reasonably sure it heard."""
    segments, _info = model.transcribe(
        audio,
        beam_size=1,
        without_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=lyrics_engine.NO_SPEECH_DROP,
        log_prob_threshold=lyrics_engine.LOGPROB_DROP,
    )
    heard: list[str] = []
    for segment in segments:
        if segment.no_speech_prob >= lyrics_engine.NO_SPEECH_DROP:
            continue
        if segment.avg_logprob <= SEGMENT_MIN_LOGPROB:
            continue
        if (getattr(segment, "compression_ratio", 0.0) or 0.0) >= SEGMENT_MAX_COMPRESSION:
            continue
        heard.extend(word.strip(".,!?;:\"'").lower() for word in segment.text.split())
    heard = [word for word in heard if word]
    return len(heard), len(set(heard))


def detect(file_path: str, duration_seconds: float | None, model_name: str) -> dict:
    """Listen for the flags. Returns {"vocal_state", "language",
    "language_confidence", "words"}; vocal_state None when undecided."""
    from app.services.audio_features import probe_duration

    duration = float(duration_seconds or 0.0) or probe_duration(file_path) or 0.0
    model = lyrics_engine.load_model(model_name)
    most_words = 0
    language = None
    confidence = 0.0
    state = None
    positions = WINDOW_POSITIONS if duration > WINDOW_SECONDS * 2 else (0.0,)
    for index, fraction in enumerate(positions):
        if duration > WINDOW_SECONDS * 2:
            start = max(0.0, min(duration - WINDOW_SECONDS, fraction * duration - WINDOW_SECONDS / 2))
            audio = _decode_window(file_path, start, WINDOW_SECONDS)
        else:
            audio = _decode_window(file_path, 0.0, min(duration or WINDOW_SECONDS, WINDOW_SECONDS))
        if audio.size < 16000:
            continue
        if index == 0:
            detected = model.detect_language(audio)
            # faster-whisper returns (language, probability, all_probabilities).
            language = detected[0] if detected else None
            confidence = float(detected[1]) if detected and len(detected) > 1 else 0.0
        words, distinct = _count_words(model, audio)
        most_words = max(most_words, words)
        if words >= MIN_WORDS_VOCAL and distinct >= MIN_DISTINCT_WORDS_VOCAL:
            state = VOCAL
            break
    if state is None and most_words <= MAX_WORDS_INSTRUMENTAL:
        state = INSTRUMENTAL
    keep_language = state == VOCAL and language and confidence >= LANGUAGE_MIN_CONFIDENCE
    return {
        "vocal_state": state,
        "language": language if keep_language else None,
        "language_confidence": round(confidence, 3) if keep_language else None,
        "words": most_words,
    }


def flags_from_lyrics_result(result: dict) -> dict:
    """What a full lyrics pass tells us, in the shape `apply_detected` takes."""
    if result.get("ok"):
        language = result.get("language")
        confidence = float(result.get("language_probability") or 0.0)
        keep = language and confidence >= LANGUAGE_MIN_CONFIDENCE
        return {
            "vocal_state": VOCAL,
            "language": language if keep else None,
            "language_confidence": round(confidence, 3) if keep else None,
            "explicit_state": explicit_from_text(result.get("plain")),
        }
    if result.get("instrumental"):
        return {"vocal_state": INSTRUMENTAL}
    return {}


def apply_detected(db: Session, track: Track, **flags) -> bool:
    """Record what the server detected, unless an admin has spoken. Only the
    keys given are touched; None values are skipped (a detection that could
    not decide must not erase an earlier one). Returns whether anything
    changed; the caller commits."""
    if track.flags_set_by == SET_BY_ADMIN:
        track.flags_checked_at = datetime.utcnow()
        return False
    changed = False
    for key in ("vocal_state", "language", "language_confidence", "explicit_state"):
        value = flags.get(key)
        if value is None:
            continue
        if getattr(track, key) != value:
            setattr(track, key, value)
            changed = True
    if changed:
        track.flags_set_by = SET_BY_DETECTED
    track.flags_checked_at = datetime.utcnow()
    return changed


def set_by_admin(db: Session, track: Track, *, vocal_state=..., language=..., explicit_state=...) -> None:
    """An admin's word, which the server will not overwrite. Ellipsis
    leaves a flag as it is; None clears it."""
    if vocal_state is not ...:
        if vocal_state is not None and vocal_state not in VOCAL_STATES:
            raise ValueError("vocal_state must be vocal or instrumental")
        track.vocal_state = vocal_state
    if language is not ...:
        track.language = (language or None) and str(language).strip().lower()[:8]
        track.language_confidence = 1.0 if track.language else None
    if explicit_state is not ...:
        if explicit_state is not None and explicit_state not in EXPLICIT_STATES:
            raise ValueError("explicit_state must be explicit or clean")
        track.explicit_state = explicit_state
    track.flags_set_by = SET_BY_ADMIN
    track.flags_checked_at = datetime.utcnow()
    db.commit()


def note_lyrics_text(db: Session, track_id: int, plain: str | None, *, commit: bool = True) -> None:
    """Lyrics text arrived, changed or went: re-read the explicit flag from
    it. Words also mean the track is vocal; no words clears a detected
    explicit flag (an admin's stands). The scanner calls this inside its own
    batch and commits itself."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if track is None:
        return
    changed = False
    if plain and plain.strip():
        changed = apply_detected(db, track, explicit_state=explicit_from_text(plain), vocal_state=VOCAL)
    elif track.explicit_state is not None and track.flags_set_by != SET_BY_ADMIN:
        track.explicit_state = None
        changed = True
    if changed and commit:
        db.commit()


def flags_payload(track: Track) -> dict:
    return {
        "vocal_state": track.vocal_state,
        "language": track.language,
        "language_confidence": track.language_confidence,
        "explicit_state": track.explicit_state,
        "set_by": track.flags_set_by,
    }
