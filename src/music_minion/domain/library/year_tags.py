"""Trim full-date year tags (2026-10-16) down to the year (2026).

scdl writes the SoundCloud upload date as YYYY-MM-DD, and Serato's Year column
cuts that to 6 characters ("2026-1"). Only the year tag is touched: TDRC (TYER
on ID3v2.3) for MP3, ©day for M4A. Release/original dates (TDRL, TDOR) and
every other frame or atom (Serato data, artwork, key, BPM) are preserved.

Usage: python -m music_minion.domain.library.year_tags <folder>... [--dry-run]
"""

import argparse
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from loguru import logger
from mutagen import MutagenError
from mutagen.id3 import ID3, TDRC, ID3NoHeaderError
from mutagen.mp4 import MP4

from music_minion.domain.metadata_cleanup.records import list_audio

_FULL_DATE_RE = re.compile(r"^(\d{4})-")


def year_only(value: str) -> str | None:
    """'2026-10-16' -> '2026'; None when the value is already a bare year (or junk)."""
    match = _FULL_DATE_RE.match(value.strip())
    return match.group(1) if match else None


def _id3_year(path: Path) -> str | None:
    try:
        frame = ID3(path).get("TDRC")
    except ID3NoHeaderError:
        return None
    return year_only(str(frame.text[0])) if frame and frame.text else None


def _mp4_year(path: Path) -> str | None:
    values = (MP4(path).tags or {}).get("©day")
    return year_only(str(values[0])) if values else None


def _write_id3(temp: Path, year: str) -> None:
    tags = ID3(temp)
    version = tags.version[1]
    tags.delall("TDRC")
    tags.add(TDRC(encoding=3, text=[year]))
    tags.save(temp, v2_version=4 if version >= 4 else 3)


def _write_mp4(temp: Path, year: str) -> None:
    audio = MP4(temp)
    audio.tags["©day"] = [year]
    audio.save()


_FORMATS: dict[
    str, tuple[Callable[[Path], str | None], Callable[[Path, str], None]]
] = {
    ".mp3": (_id3_year, _write_id3),
    ".m4a": (_mp4_year, _write_mp4),
}


def trim_file(path: Path, dry_run: bool = False) -> str | None:
    """Rewrite the year tag if it holds a full date. Returns the new year, or
    None when the file was already fine. Atomic: copy -> edit temp -> replace."""
    read, write = _FORMATS[path.suffix.lower()]
    year = read(path)
    if year is None or dry_run:
        return year
    temp = path.with_name(path.name + ".tmp")
    try:
        shutil.copy2(path, temp)
        write(temp, year)
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return year


def trim_folder(folder: Path, dry_run: bool = False) -> tuple[int, int]:
    """Trim every MP3/M4A under folder. Returns (changed, failed)."""
    changed = failed = 0
    for path in list_audio(folder):
        try:
            if trim_file(path, dry_run):
                changed += 1
        except (MutagenError, OSError):
            logger.exception(f"year_tags: could not trim date on {path}")
            failed += 1
    return changed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Trim YYYY-MM-DD year tags to YYYY")
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Count, don't write")
    args = parser.parse_args()
    results = [trim_folder(folder, args.dry_run) for folder in args.folders]
    changed, failed = (sum(column) for column in zip(*results))
    verb = "would trim" if args.dry_run else "trimmed"
    logger.info(f"Year tags: {verb} {changed}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
