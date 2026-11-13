"""Track notes: the file's COMMENT tag, the same field Serato shows as Comment.

MP3: the COMM frame with an empty description (Serato's). Other COMM frames
(iTunNORM, ID3v1 Comment, ...) are left alone.
M4A: the ©cmt atom.
Writes are atomic (copy -> edit temp -> os.replace); every other tag is kept.
"""

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from mutagen.id3 import COMM, ID3, ID3NoHeaderError
from mutagen.mp4 import MP4

NOTE_SUFFIXES = (".mp3", ".m4a")
_MP4_COMMENT = "©cmt"


def supports_notes(path: Path) -> bool:
    return path.suffix.lower() in NOTE_SUFFIXES


def _serato_comms(tags: ID3) -> list[COMM]:
    return [frame for frame in tags.getall("COMM") if frame.desc == ""]


def _read_id3(path: Path) -> str:
    try:
        frames = _serato_comms(ID3(path))
    except ID3NoHeaderError:
        return ""
    return str(frames[0]) if frames else ""


def _read_mp4(path: Path) -> str:
    tags = MP4(path).tags
    values = (tags or {}).get(_MP4_COMMENT) or [""]
    return str(values[0])


def _write_id3(temp: Path, notes: str) -> None:
    try:
        tags = ID3(temp)
    except ID3NoHeaderError:
        tags = ID3()
    for frame in _serato_comms(tags):
        tags.delall(frame.HashKey)
    if notes:
        tags.add(COMM(encoding=3, lang="eng", desc="", text=[notes]))
    tags.save(temp, v2_version=4 if tags.version[1] >= 4 else 3)


def _write_mp4(temp: Path, notes: str) -> None:
    audio = MP4(temp)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.pop(_MP4_COMMENT, None)
    if notes:
        audio.tags[_MP4_COMMENT] = [notes]
    audio.save()


_READERS: dict[str, Callable[[Path], str]] = {".mp3": _read_id3, ".m4a": _read_mp4}
_WRITERS: dict[str, Callable[[Path, str], None]] = {
    ".mp3": _write_id3,
    ".m4a": _write_mp4,
}


def read_notes(path: Path) -> str:
    """The comment text, or "" when the file has none."""
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"read_notes: unsupported audio format for {path}")
    return reader(path)


def write_notes(path: Path, notes: str) -> None:
    """Replace the comment; empty notes delete it."""
    writer = _WRITERS.get(path.suffix.lower())
    if writer is None:
        raise ValueError(f"write_notes: unsupported audio format for {path}")
    temp = path.with_name(path.name + ".tmp")
    try:
        shutil.copy2(path, temp)
        writer(temp, notes)
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
