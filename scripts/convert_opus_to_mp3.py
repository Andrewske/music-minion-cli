"""Convert .opus library tracks to MP3 320 (Serato-compatible).

Opus files in this library carry no embedded tags; all metadata lives in the
music-minion DB. So we transcode opus -> mp3 320 CBR, write the DB's title/
artist/album/genre/year into the new file's ID3 tags (so Serato shows real
names, not filenames), copy any attached album art, verify the output, update
the DB local_path, then delete the original opus.

Usage:
    uv run python scripts/convert_opus_to_mp3.py --test    # 2 files -> /tmp, no DB change
    uv run python scripts/convert_opus_to_mp3.py --dry-run # list what would convert
    uv run python scripts/convert_opus_to_mp3.py --apply   # do it for real
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from music_minion.core import database as db


def get_opus_tracks() -> list[dict]:
    """Return DB tracks whose local_path is a .opus file that exists on disk."""
    with db.get_db_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, artist, album, genre, year, bpm, local_path
               FROM tracks WHERE lower(local_path) LIKE '%.opus'"""
        ).fetchall()
    tracks = [dict(r) for r in rows]
    return [t for t in tracks if os.path.exists(t["local_path"])]


def build_ffmpeg_cmd(src: Path, dst: Path, meta: dict) -> list[str]:
    """ffmpeg command: opus -> mp3 320 CBR, DB tags, optional album art."""
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    # audio stream first, optional attached picture second (? = skip if absent)
    cmd += ["-map", "0:a:0", "-map", "0:v:0?"]
    cmd += ["-c:a", "libmp3lame", "-b:a", "320k", "-c:v", "copy"]
    cmd += ["-id3v2_version", "3", "-map_metadata", "-1"]
    for key, val in (
        ("title", meta.get("title")),
        ("artist", meta.get("artist")),
        ("album", meta.get("album")),
        ("genre", meta.get("genre")),
        ("date", meta.get("year")),
    ):
        if val:
            cmd += ["-metadata", f"{key}={val}"]
    if meta.get("bpm"):
        cmd += ["-metadata", f"TBPM={int(meta['bpm'])}"]
    cmd.append(str(dst))
    return cmd


def verify_mp3(path: Path) -> bool:
    """True if file exists and ffprobe reports a positive audio duration."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip()) > 0
    except ValueError:
        return False


def convert_one(src: Path, dst: Path, meta: dict) -> bool:
    """Convert a single file; return True if the output is valid."""
    res = subprocess.run(
        build_ffmpeg_cmd(src, dst, meta), capture_output=True, text=True
    )
    if res.returncode != 0:
        tail = res.stderr.strip().splitlines()[-1:] or ["unknown error"]
        print(f"  FFMPEG FAIL {src.name}: {tail[0]}")
        return False
    return verify_mp3(dst)


def update_db_path(track_id: int, new_path: str) -> None:
    with db.get_db_connection() as conn:
        conn.execute(
            "UPDATE tracks SET local_path = ?, file_mtime = ? WHERE id = ?",
            (new_path, os.path.getmtime(new_path), track_id),
        )
        conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--test", action="store_true", help="2 files -> /tmp, no DB change")
    g.add_argument("--dry-run", action="store_true", help="list candidates")
    g.add_argument("--apply", action="store_true", help="convert for real")
    args = ap.parse_args()

    tracks = get_opus_tracks()
    print(f"opus tracks on disk: {len(tracks)}")

    if args.dry_run:
        for t in tracks[:10]:
            print(" ", t["local_path"])
        if len(tracks) > 10:
            print(f"  ... and {len(tracks) - 10} more")
        return 0

    if args.test:
        tmp = Path("/tmp/opus_convert_test")
        tmp.mkdir(exist_ok=True)
        for t in tracks[:2]:
            src = Path(t["local_path"])
            dst = tmp / (src.stem + ".mp3")
            ok = convert_one(src, dst, t)
            kb = dst.stat().st_size // 1024 if dst.exists() else 0
            print(f"  {'OK ' if ok else 'BAD'} {dst.name} ({kb} KB)")
        print("Inspect /tmp/opus_convert_test/ then run --apply")
        return 0

    # --apply
    ok_count = fail_count = 0
    failed: list[str] = []
    for i, t in enumerate(tracks, 1):
        src = Path(t["local_path"])
        dst = src.with_suffix(".mp3")
        if convert_one(src, dst, t):
            update_db_path(t["id"], str(dst))
            src.unlink()  # delete opus only after verified output + DB update
            ok_count += 1
        else:
            fail_count += 1
            failed.append(str(src))
        if i % 25 == 0:
            print(f"  {i}/{len(tracks)} ({ok_count} ok, {fail_count} fail)")
    print(f"DONE: {ok_count} converted, {fail_count} failed")
    for f in failed:
        print("  FAILED:", f)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
