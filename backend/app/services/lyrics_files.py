"""Lyrics the listener's files already carry.

Two places, read in this order: a lyrics tag inside the file, then a sidecar
file beside it. Both are the listener's own material, read the way the
scanner reads a title, and neither involves anything leaving the server.

Tags, by container (mutagen sees all of them through its generic reader):

    MP3 / WAV / AIFF   ID3 USLT (plain) and SYLT (timed, in milliseconds)
    M4A                the ©lyr atom
    FLAC / Ogg / Opus  LYRICS, UNSYNCEDLYRICS or SYNCEDLYRICS Vorbis comments

Plain text in any of these is often LRC — "[01:23.45] a line" — because the
tagging tools write it that way, so every text goes through the LRC parser,
which hands back both the timed lines and the plain words.
"""

import logging
import re
from pathlib import Path

from mutagen import File as MutagenFile

logger = logging.getLogger(__name__)

# Sidecar names tried, in order, next to the audio file.
SIDECAR_SUFFIXES = (".lrc", ".LRC", ".txt", ".TXT")

# The longest lyrics text stored, in characters. A whole libretto fits; a
# tag that is really a misfiled binary does not.
MAX_LYRICS_CHARS = 64_000

_LRC_TIME = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
_LRC_META = re.compile(r"^\[(ar|ti|al|au|by|re|ve|length|offset|la|tool|#)[^\]]*\]\s*$", re.I)
_LRC_WORD_TIME = re.compile(r"<\d{1,2}:\d{2}(?:[.:]\d{1,3})?>")


def _seconds(minutes: str, seconds: str, fraction: str | None) -> float:
    frac = 0.0
    if fraction:
        frac = int(fraction) / (10 ** len(fraction))
    return int(minutes) * 60 + int(seconds) + frac


def parse_lrc(text: str) -> dict:
    """Timed lines and plain text from LRC, or plain text alone when the text
    carries no timestamps.

    Handles several timestamps on one line (a repeated chorus), the metadata
    tags at the top, an `[offset:]` in milliseconds, and "enhanced" word tags,
    which are dropped to line level. Lines come back sorted by time. Blank
    lines inside the lyrics are kept as empty lines in the plain text, but not
    as timed entries.
    """
    if not text:
        return {"plain": "", "synced": None}

    offset_ms = 0
    timed: list[tuple[float, str]] = []
    plain_lines: list[str] = []
    saw_time = False

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if _LRC_META.match(line):
            match = re.match(r"^\[offset:\s*([+-]?\d+)\]", line, re.I)
            if match:
                offset_ms = int(match.group(1))
            continue

        stamps = _LRC_TIME.findall(line)
        words = _LRC_TIME.sub("", line)
        words = _LRC_WORD_TIME.sub("", words).strip()
        words = " ".join(words.split())

        if stamps:
            saw_time = True
            for minutes, seconds, fraction in stamps:
                at = _seconds(minutes, seconds, fraction) - offset_ms / 1000.0
                if words:
                    timed.append((max(0.0, round(at, 3)), words))
            if words:
                plain_lines.append(words)
            continue

        plain_lines.append(words)

    # Trim leading and trailing blank lines; collapse runs of blanks to one.
    cleaned: list[str] = []
    for line in plain_lines:
        if not line and (not cleaned or not cleaned[-1]):
            continue
        cleaned.append(line)
    while cleaned and not cleaned[-1]:
        cleaned.pop()

    plain = "\n".join(cleaned)
    if not saw_time:
        return {"plain": plain, "synced": None}

    timed.sort(key=lambda pair: pair[0])
    # The plain text of a timed lyric is its lines in time order, once each
    # where a line was stamped several times in a row.
    ordered: list[str] = []
    for _at, words in timed:
        if not ordered or ordered[-1] != words:
            ordered.append(words)
    return {"plain": "\n".join(ordered), "synced": [[at, words] for at, words in timed]}


def _text_of(value) -> str | None:
    """One tag value as text, whatever shape mutagen hands it in."""
    if value is None:
        return None
    if hasattr(value, "text"):
        value = value.text
    if isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if item is not None and str(item).strip()]
        value = "\n".join(parts)
    text = str(value).replace("\x00", "\n").strip()
    return text or None


def _sylt_lines(frame) -> list[list] | None:
    """A SYLT frame's (text, time) pairs as [seconds, line] lines.

    Format 2 is milliseconds; format 1 is MPEG frames, which this does not
    convert (rare in the wild, and wrong more often than right when it is).
    """
    if getattr(frame, "format", 2) != 2:
        return None
    lines = []
    for text, when in getattr(frame, "text", []) or []:
        words = " ".join(str(text).replace("\x00", " ").split())
        if words:
            lines.append([round(int(when) / 1000.0, 3), words])
    lines.sort(key=lambda pair: pair[0])
    return lines or None


def extract_lyrics_from_tags(file_path: str) -> dict | None:
    """{"plain", "synced"} from the file's own tags, or None when it has none."""
    try:
        audio = MutagenFile(file_path)
    except Exception as error:  # noqa: BLE001
        logger.debug("Could not open %s for lyrics: %s", file_path, error)
        return None
    if audio is None or not audio.tags:
        return None

    tags = audio.tags
    plain_text: str | None = None
    synced: list[list] | None = None

    # ID3: SYLT for timing, USLT for words.
    for key in list(tags.keys()):
        upper = str(key).upper()
        if upper.startswith("SYLT") and synced is None:
            synced = _sylt_lines(tags[key])
        elif upper.startswith("USLT") and plain_text is None:
            plain_text = _text_of(tags[key])

    # MP4 and Vorbis: one text field, which may be LRC. Looked up by walking
    # the keys: a Vorbis comment refuses an `in` check for a key with a
    # character it does not allow, and the MP4 atom name is one of those.
    if plain_text is None:
        wanted = ("\xa9lyr", "lyrics", "unsyncedlyrics", "syncedlyrics")
        for key in list(tags.keys()):
            if str(key).lower() in wanted:
                plain_text = _text_of(tags[key])
                if plain_text:
                    break

    if plain_text is None and synced is None:
        return None

    parsed = parse_lrc(plain_text or "")
    if synced is None:
        synced = parsed["synced"]
    plain = parsed["plain"] or "\n".join(line for _at, line in (synced or []))
    if not plain:
        return None
    return {"plain": plain[:MAX_LYRICS_CHARS], "synced": synced}


def sidecar_path_for(file_path: str) -> Path | None:
    """The .lrc or .txt beside the track, if there is one."""
    stem = Path(file_path).with_suffix("")
    for suffix in SIDECAR_SUFFIXES:
        candidate = stem.with_name(stem.name + suffix)
        if candidate.is_file():
            return candidate
    return None


def is_sidecar_name(path) -> bool:
    return Path(path).suffix in SIDECAR_SUFFIXES


def read_sidecar(path: Path) -> dict | None:
    try:
        raw = path.read_bytes()[: MAX_LYRICS_CHARS * 4]
    except OSError as error:
        logger.debug("Could not read sidecar %s: %s", path, error)
        return None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    parsed = parse_lrc(text)
    if not parsed["plain"]:
        return None
    return {"plain": parsed["plain"][:MAX_LYRICS_CHARS], "synced": parsed["synced"]}


def lyrics_from_file(file_path: str) -> dict | None:
    """What the listener's files say: {"source", "plain", "synced"}, or None.

    The tag wins over the sidecar when both exist, because the tag travels
    with the file wherever it goes.
    """
    from_tags = extract_lyrics_from_tags(file_path)
    if from_tags:
        return {"source": "embedded", **from_tags}
    sidecar = sidecar_path_for(file_path)
    if sidecar is not None:
        from_sidecar = read_sidecar(sidecar)
        if from_sidecar:
            return {"source": "sidecar", **from_sidecar}
    return None
