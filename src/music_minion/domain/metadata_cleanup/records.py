"""Read MP3 tags and build JSON-serializable input records."""

import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from mutagen.id3 import ID3, ID3NoHeaderError

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

Record = dict[str, Any]


def clean_filename(path: Path) -> str:
    """Strip the 'Mon YY_' and 'NN. ' prefixes yt-dlp/Serato leave on files."""
    stem = _MONTH_PREFIX_RE.sub("", path.stem)
    return _TRACK_NUMBER_RE.sub("", stem).strip()


def _first_frame(tags: ID3, frame_id: str) -> Optional[str]:
    frames = tags.getall(frame_id)
    if not frames:
        return None
    frame = frames[0]
    return getattr(frame, "url", None) or str(frame)


def read_tags(path: Path) -> dict[str, str]:
    """Return the text tags relevant to cleanup (missing frames omitted)."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return {}
    frame_ids = {**_TEXT_FRAMES, "comment": "COMM", "source_url": "WOAF"}
    values = {name: _first_frame(tags, fid) for name, fid in frame_ids.items()}
    return {name: value for name, value in values.items() if value}


def list_mp3s(folder: Path) -> list[Path]:
    """All MP3s except Syncthing conflict copies."""
    return sorted(p for p in folder.rglob("*.mp3") if ".sync-conflict-" not in p.name)


def track_id(path: Path) -> str:
    """Stable record id: path relative to the EDM library root."""
    return str(path.relative_to(MUSIC_ROOT))


def build_record(
    path: Path, tags: dict[str, str], soundcloud: Optional[dict[str, Any]], raw: bool
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
