from pathlib import Path
from typing import Union

SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".mp4",
    ".aac",
    ".ogg",
    ".wav",
    ".opus",
}


def is_supported_audio_file(path: Union[str, Path]) -> bool:
    file_path = Path(path)
    return file_path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS