"""Lyrics produced on this server, from the listener's own audio.

Two jobs, both built on one speech model:

- *Timing* for lyrics whose words are already known (a plain lyrics tag, a
  sidecar without timestamps, something a person pasted). The model is run
  with the known text as its prompt, its words are matched to the known
  lines, and each line takes the time of its first matched word. The words
  stay exactly as they were; only the timing is new.
- *Transcription* for tracks with no words anywhere: the model's own text and
  timing, with every segment it judged to be no speech dropped, so an
  instrumental yields nothing rather than guesses.

The model is OpenAI's Whisper through faster-whisper (CTranslate2), run on
the CPU with 8-bit weights. Everything in this stack — Whisper's weights,
faster-whisper, CTranslate2, the tokenizer and runtime libraries — is under
MIT, BSD or Apache terms, chosen so that this module can live in anything
Adjacent sells. Audio is decoded by the server's own ffmpeg, as a
subprocess, so nothing here links against it.

The dependency is optional at import time: a server without it answers
"unsupported" and everything else keeps working.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Where the model weights live: inside the data volume, so a container
# restart does not download them again.
MODELS_DIR = Path("data/models")

# The models a server may pick. `base` is the default: three times faster
# than `small` and a third of its size, which on a NAS is the difference
# between "a song in a minute" and "a song in four".
LYRICS_MODELS = ("base", "small")
DEFAULT_LYRICS_MODEL = "base"

# A 30-second window is treated as silence only when the model BOTH rates it
# this likely to be no speech AND was this unsure of the words it heard in
# it — faster-whisper's own rule. Singing alone routinely rates 0.6–0.65 "no
# speech" while the words are read with good confidence; dropping on the
# no-speech score by itself threw away half the words of a real song and
# made lyrics stop partway through. Measured on this machine: 419 words
# kept under this rule, 222 under the one-sided one.
NO_SPEECH_DROP = 0.6
LOGPROB_DROP = -1.0
# Fewer words than this per minute of audio and the track is an
# instrumental: a sine tone yields one stray "You" in ninety seconds, a
# sung song thirty to a hundred words a minute.
MIN_WORDS_PER_MINUTE = 2.0
# Whisper's failure mode on music is a loop: the same line over and over.
# A chorus repeats a line a few times; a loop repeats it for the whole
# rest of the track. Consecutive copies beyond this many are dropped.
MAX_CONSECUTIVE_REPEATS = 2
# Fewer matched words than this and a timing pass is reported as failed
# rather than stored: the audio does not carry the words it was given.
MIN_ALIGN_COVERAGE = 0.35
# Fewer than this many words and a transcription is "no vocals found".
MIN_TRANSCRIBED_WORDS = 6

_model_guard = threading.Lock()
_models: dict[str, object] = {}


def transcriber_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def decode_audio(file_path: str) -> "numpy.ndarray":
    """16 kHz mono float samples, by way of the server's ffmpeg."""
    import numpy as np

    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", file_path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=600,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"ffmpeg could not decode the file: {result.stderr.decode(errors='ignore')[-200:]}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def _threads() -> int:
    # Half the cores, at least one, at most four: the music must keep
    # transcoding while this runs.
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def load_model(name: str):
    """The model, loaded once per process; downloaded on first use."""
    from faster_whisper import WhisperModel

    if name not in LYRICS_MODELS:
        name = DEFAULT_LYRICS_MODEL
    with _model_guard:
        model = _models.get(name)
        if model is None:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            model = WhisperModel(
                name,
                device="cpu",
                compute_type="int8",
                cpu_threads=_threads(),
                download_root=str(MODELS_DIR),
            )
            _models[name] = model
    return model


def segment_is_speech(no_speech_prob: float, avg_logprob: float) -> bool:
    """Whether a window carries words: see NO_SPEECH_DROP."""
    return not (no_speech_prob > NO_SPEECH_DROP and avg_logprob < LOGPROB_DROP)


def collapse_repeats(segments: list[dict]) -> list[dict]:
    """Drop the copies of a line repeated more than MAX_CONSECUTIVE_REPEATS
    times in a row — Whisper stuck on a phrase, not a chorus."""
    kept: list[dict] = []
    run = 0
    for segment in segments:
        text = " ".join(segment["text"].lower().split())
        if kept and " ".join(kept[-1]["text"].lower().split()) == text:
            run += 1
            if run >= MAX_CONSECUTIVE_REPEATS:
                continue
        else:
            run = 0
        kept.append(segment)
    return kept


def looks_instrumental(words: int, duration_seconds: float) -> bool:
    minutes = max(float(duration_seconds or 0) / 60.0, 1 / 60)
    return words < MIN_TRANSCRIBED_WORDS or words / minutes < MIN_WORDS_PER_MINUTE


def run_model(model, audio, prompt: str | None = None) -> dict:
    """Segments and words from the model, silence windows dropped."""
    segments, info = model.transcribe(
        audio,
        beam_size=1,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=NO_SPEECH_DROP,
        log_prob_threshold=LOGPROB_DROP,
        initial_prompt=prompt or None,
    )
    kept = []
    dropped = 0
    for segment in segments:
        if not segment_is_speech(segment.no_speech_prob, segment.avg_logprob):
            dropped += 1
            continue
        words = [
            {"word": word.word.strip(), "start": float(word.start), "end": float(word.end)}
            for word in (segment.words or [])
            if word.word and word.word.strip()
        ]
        kept.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": " ".join(segment.text.split()),
                "words": words,
                "avg_logprob": float(segment.avg_logprob),
            }
        )
    before = len(kept)
    kept = collapse_repeats(kept)
    return {
        "segments": kept,
        "dropped": dropped,
        "repeats_dropped": before - len(kept),
        "duration": float(getattr(info, "duration", 0.0) or 0.0),
        "language": getattr(info, "language", None),
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
    }


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def align_lines(known_text: str, segments: list[dict]) -> dict:
    """Timing for known lines, from the model's words.

    The known words and the model's words are matched as two sequences;
    each known line takes the time of its first matched word. A line with
    no match of its own is placed between its neighbours. Returns the timed
    lines and how much of the known text was matched, which the caller
    uses to decide whether the audio carried these words at all.
    """
    lines = [" ".join(line.split()) for line in known_text.replace("\r", "").split("\n")]
    lines = [line for line in lines if line]
    known_words: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        for word in line.split():
            normalized = _norm(word)
            if normalized:
                known_words.append((index, normalized))

    heard = [(_norm(w["word"]), w["start"]) for s in segments for w in s["words"]]
    heard = [(word, start) for word, start in heard if word]

    if not known_words or not heard:
        return {"synced": None, "coverage": 0.0}

    matcher = difflib.SequenceMatcher(
        a=[word for _line, word in known_words], b=[word for word, _start in heard], autojunk=False
    )
    first_time: dict[int, float] = {}
    matched = 0
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            line_index = known_words[block.a + offset][0]
            start = heard[block.b + offset][1]
            matched += 1
            if line_index not in first_time or start < first_time[line_index]:
                first_time[line_index] = start

    coverage = matched / len(known_words)

    # Lines the matcher could not place sit between the lines around them.
    times: list[float | None] = [first_time.get(index) for index in range(len(lines))]
    for index, value in enumerate(times):
        if value is not None:
            continue
        before = next((times[j] for j in range(index - 1, -1, -1) if times[j] is not None), None)
        after = next((times[j] for j in range(index + 1, len(times)) if times[j] is not None), None)
        if before is None and after is None:
            times[index] = 0.0
        elif before is None:
            times[index] = max(0.0, after - 2.0)
        elif after is None:
            times[index] = before + 2.0
        else:
            times[index] = (before + after) / 2.0

    # Keep time moving forward: a mismatched word can put a line before the
    # one above it, and the display cannot show that.
    synced: list[list] = []
    last = -1.0
    for index, line in enumerate(lines):
        at = max(float(times[index]), last + 0.01) if last >= 0 else max(0.0, float(times[index]))
        synced.append([round(at, 3), line])
        last = at
    return {"synced": synced, "coverage": round(coverage, 3)}


def transcription_lines(segments: list[dict]) -> dict:
    """The model's own text as timed lines: one per segment."""
    synced = [[round(s["start"], 3), s["text"]] for s in segments if s["text"]]
    words = sum(len(s["words"]) for s in segments)
    if not synced:
        return {"synced": None, "plain": "", "words": words, "confidence": None}
    logprobs = [s["avg_logprob"] for s in segments]
    # A log-probability of 0 is certainty, -1 is the drop threshold; map the
    # average onto 0–1 for the clients.
    confidence = max(0.0, min(1.0, 1.0 + sum(logprobs) / len(logprobs)))
    return {
        "synced": synced,
        "plain": "\n".join(line for _at, line in synced),
        "words": words,
        "confidence": round(confidence, 3),
    }


def generate(file_path: str, *, model_name: str, known_text: str | None = None) -> dict:
    """Run the model over a file.

    With `known_text`: time those lines (result "aligned"). Without: produce
    text and timing (result "transcribed"). Either way the result carries
    `ok`, and when not ok a `reason` the clients can show.
    """
    model = load_model(model_name)
    audio = decode_audio(file_path)
    if known_text:
        run = run_model(model, audio, prompt=known_text[:800])
        aligned = align_lines(known_text, run["segments"])
        if aligned["synced"] is None or aligned["coverage"] < MIN_ALIGN_COVERAGE:
            return {
                "ok": False,
                "reason": "The audio does not match these lyrics closely enough to time them.",
                "coverage": aligned["coverage"],
                "language": run["language"],
            }
        return {
            "ok": True,
            "kind": "aligned",
            "synced": aligned["synced"],
            "plain": known_text,
            "confidence": aligned["coverage"],
            "language": run["language"],
            "model": model_name,
        }

    run = run_model(model, audio)
    lines = transcription_lines(run["segments"])
    if not lines["synced"] or looks_instrumental(lines["words"], run["duration"] or len(audio) / 16000):
        return {
            "ok": False,
            "reason": "No vocals were found in this track.",
            "language": run["language"],
            "dropped": run["dropped"],
        }
    return {
        "ok": True,
        "kind": "transcribed",
        "synced": lines["synced"],
        "plain": lines["plain"],
        "confidence": lines["confidence"],
        "language": run["language"],
        "model": model_name,
    }
