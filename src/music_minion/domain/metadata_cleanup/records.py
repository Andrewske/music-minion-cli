"""Read MP3 (ID3) and M4A (MP4) tags and build JSON-serializable input records."""

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Tags

from music_minion.core.config import get_data_dir

MUSIC_ROOT = Path.home() / "Music" / "EDM"
WORK_DIR = get_data_dir() / "metadata-cleanup"

_TRACK_NUMBER_RE = re.compile(r"^\d+\.\s+")
_MONTH_PREFIX_RE = re.compile(r"^[A-Za-z]+ \d+_")
_TEXT_FRAMES = {
    "title": "TIT2",
    "artist": "TPE1",
    "album_artist": "TPE2",
    "remixer": "TPE4",
    "genre": "TCON",
    "date": "TDRC",
}
AUDIO_SUFFIXES = (".mp3", ".m4a")
MP4_FREEFORM = "----:com.apple.iTunes:"
MP4_REMIXER = MP4_FREEFORM + "REMIXER"  # Picard convention
_MP4_ATOMS = {
    "title": "©nam",
    "artist": "©ART",
    "album_artist": "aART",
    "genre": "©gen",
    "date": "©day",
    "comment": "©cmt",
    "remixer": MP4_REMIXER,
}
# scdl writes the SoundCloud URL to both; the freeform atom wins.
_MP4_SOURCE_URL_ATOMS = (MP4_FREEFORM + "WWWAUDIOFILE", "purl")

Record = dict[str, Any]


def clean_filename(path: Path) -> str:
    """Strip the 'Mon YY_' and 'NN. ' prefixes yt-dlp/Serato leave on files."""
    stem = _MONTH_PREFIX_RE.sub("", path.stem)
    return _TRACK_NUMBER_RE.sub("", stem).strip()


def _first_frame(tags: ID3, frame_id: str) -> str | None:
    frames = tags.getall(frame_id)
    if not frames:
        return None
    frame = frames[0]
    return getattr(frame, "url", None) or str(frame)


def _read_id3(path: Path) -> dict[str, str]:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return {}
    frame_ids = {**_TEXT_FRAMES, "comment": "COMM", "source_url": "WOAF"}
    values = {name: _first_frame(tags, fid) for name, fid in frame_ids.items()}
    return {name: value for name, value in values.items() if value}


def _first_atom(tags: MP4Tags, key: str) -> str | None:
    """First value of an atom; freeform (MP4FreeForm) bytes decode as UTF-8."""
    values = tags.get(key) or []
    if not values:
        return None
    value = values[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _read_mp4(path: Path) -> dict[str, str]:
    tags = MP4(path).tags
    if tags is None:
        return {}
    values = {name: _first_atom(tags, key) for name, key in _MP4_ATOMS.items()}
    urls = (_first_atom(tags, key) for key in _MP4_SOURCE_URL_ATOMS)
    values["source_url"] = next((url for url in urls if url), None)
    return {name: value for name, value in values.items() if value}


def read_tags(path: Path) -> dict[str, str]:
    """Return the text tags relevant to cleanup (missing tags omitted).

    Both formats map to the same keys: title, artist, album_artist, remixer,
    genre, date, comment, source_url.
    """
    suffix = path.suffix.lower()
    if suffix == ".m4a":
        return _read_mp4(path)
    if suffix == ".mp3":
        return _read_id3(path)
    raise ValueError(f"read_tags: unsupported audio format {suffix!r} for {path}")


def list_audio(folder: Path) -> list[Path]:
    """All MP3s and M4As except Syncthing conflict copies."""
    found = (p for suffix in AUDIO_SUFFIXES for p in folder.rglob(f"*{suffix}"))
    return sorted(p for p in found if ".sync-conflict-" not in p.name)


def track_id(path: Path) -> str:
    """Stable record id: path relative to the EDM library root."""
    return str(path.relative_to(MUSIC_ROOT))


def build_record(
    path: Path, tags: dict[str, str], soundcloud: dict[str, Any] | None, raw: bool
) -> Record:
    """Assemble one model input record.

    raw=True means the file's tags are still as downloaded, so they are safe
    to show the model. For gold tracks the tags are the answer and must be hidden.
    """
    return {
        "id": track_id(path),
        "filename": clean_filename(path),
        "soundcloud": soundcloud,
        "file_tags": _input_tags(tags) if raw else None,
    }


def _input_tags(tags: dict[str, str]) -> dict[str, str]:
    keep = ("title", "artist", "remixer", "genre", "comment")
    return {key: tags[key] for key in keep if key in tags}


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]
