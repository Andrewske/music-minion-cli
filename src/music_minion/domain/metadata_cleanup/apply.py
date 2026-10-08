"""Write cleaned title/artist/remixer tags to MP3s, with backups and undo.

Only TIT2, TPE1 and TPE4 are touched. Every other frame (Serato GEOB data,
artwork, key, BPM, comments) is preserved, and each file keeps its ID3 version.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from mutagen.id3 import ID3, TIT2, TPE1, TPE4

from music_minion.domain.metadata_cleanup import records

BACKUPS_DIR = records.WORK_DIR / "backups"
_FRAMES = {"title": ("TIT2", TIT2), "artist": ("TPE1", TPE1), "remixer": ("TPE4", TPE4)}


def _set_frames(tags: ID3, values: dict[str, str]) -> None:
    for key, value in values.items():
        frame_id, frame_cls = _FRAMES[key]
        tags.delall(frame_id)
        if value:
            tags.add(frame_cls(encoding=3, text=[value]))


def write_tags(path: Path, values: dict[str, str]) -> None:
    """Atomic edit: copy -> modify temp -> os.replace. mtime changes on purpose
    so music-minion's change detection re-imports the file."""
    temp = path.with_name(path.name + ".tmp")
    try:
        shutil.copy2(path, temp)
        tags = ID3(temp)
        version = tags.version[1]
        _set_frames(tags, values)
        tags.save(temp, v2_version=4 if version >= 4 else 3)
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def read_current(path: Path) -> dict[str, str]:
    tags = records.read_tags(path)
    return {key: tags.get(key, "") for key in _FRAMES}


def new_backup_dir() -> Path:
    backup = BACKUPS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, exist_ok=False)
    return backup


def apply_changes(changes: list[dict[str, Any]]) -> tuple[Path, int, list[str]]:
    """Back up then write each change. Returns (backup_dir, written, failed_ids)."""
    backup = new_backup_dir()
    written, failed = 0, []
    with open(backup / "changes.jsonl", "a") as log:
        for change in changes:
            path = records.MUSIC_ROOT / change["id"]
            entry = {
                "id": change["id"],
                "old": read_current(path),
                "new": change["new"],
            }
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            log.flush()
            try:
                write_tags(path, change["new"])
                written += 1
            except Exception:
                logger.exception(
                    f"Tag write failed for {path} (new values {change['new']})"
                )
                failed.append(change["id"])
    return backup, written, failed


def restore(backup: Path) -> int:
    """Undo an apply run by writing back the logged old values."""
    entries = records.read_jsonl(backup / "changes.jsonl")
    for entry in entries:
        write_tags(records.MUSIC_ROOT / entry["id"], entry["old"])
    return len(entries)
