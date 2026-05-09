#!/usr/bin/env python3
"""
Backfill SoundCloud artwork into local audio files missing cover art.

Queries local tracks that have a soundcloud_id but no embedded cover art,
downloads 500x500 artwork from SoundCloud, and embeds it using Mutagen.

Usage:
    uv run python scripts/backfill_artwork.py             # dry-run (default)
    uv run python scripts/backfill_artwork.py --apply     # write to files
    uv run python scripts/backfill_artwork.py --apply --limit 50  # batch test
"""

import argparse
import base64
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.library.providers.soundcloud import auth as sc_auth

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SC_API_TRACK_URL = "https://api-v2.soundcloud.com/tracks/{soundcloud_id}"
SC_API_DELAY = 0.5  # 2 req/s rate limit


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def load_access_token() -> Optional[str]:
    """Load a valid SC OAuth token, refreshing if expired."""
    token_data = sc_auth._load_user_tokens()
    if not token_data:
        logger.error("No SoundCloud token found. Run: library auth soundcloud")
        return None

    if sc_auth.is_token_expired(token_data):
        logger.info("Token expired, refreshing...")
        refreshed = sc_auth.refresh_token(token_data)
        if not refreshed:
            logger.error("Token refresh failed. Run: library auth soundcloud")
            return None
        token_data = refreshed

    return token_data["access_token"]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Resolve the SQLite database path."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "music-minion" / "music_minion.db"


def query_tracks(conn: sqlite3.Connection, limit: Optional[int]) -> list[dict]:
    """Fetch local tracks with a soundcloud_id."""
    sql = """
        SELECT id, local_path, soundcloud_id, artwork_url
        FROM tracks
        WHERE soundcloud_id IS NOT NULL
          AND local_path IS NOT NULL
        ORDER BY id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    rows = conn.execute(sql).fetchall()
    return [
        {
            "id": r[0],
            "local_path": r[1],
            "soundcloud_id": r[2],
            "artwork_url": r[3],
        }
        for r in rows
    ]


def update_artwork_url(conn: sqlite3.Connection, track_id: int, url: str) -> None:
    """Persist artwork_url back to the database."""
    conn.execute(
        "UPDATE tracks SET artwork_url = ? WHERE id = ?",
        (url, track_id),
    )


# ---------------------------------------------------------------------------
# SoundCloud API
# ---------------------------------------------------------------------------


def fetch_artwork_url(soundcloud_id: str, access_token: str) -> Optional[str]:
    """Fetch artwork_url from SC API v2 for a given track ID."""
    url = SC_API_TRACK_URL.format(soundcloud_id=soundcloud_id)
    headers = {"Authorization": f"OAuth {access_token}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("artwork_url") or data.get("user", {}).get("avatar_url")
    except requests.HTTPError as exc:
        logger.warning(
            f"SC API error for id={soundcloud_id}: HTTP {exc.response.status_code}"
        )
        return None
    except Exception as exc:
        logger.warning(f"SC API fetch failed for id={soundcloud_id}: {exc}")
        return None


def upgrade_artwork_url(url: str) -> str:
    """Replace -large suffix with -t500x500 for full-resolution art."""
    return url.replace("-large.", "-t500x500.")


def download_image(url: str) -> Optional[bytes]:
    """Download image bytes from a URL."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            logger.warning(f"Unexpected content-type '{content_type}' for {url}")
        return resp.content
    except Exception as exc:
        logger.warning(f"Image download failed for {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Cover art detection
# ---------------------------------------------------------------------------


def has_embedded_art(file_path: str) -> bool:
    """Return True if the audio file already has embedded cover art."""
    suffix = Path(file_path).suffix.lower()

    try:
        if suffix == ".mp3":
            from mutagen.id3 import ID3, ID3NoHeaderError

            try:
                tags = ID3(file_path)
            except ID3NoHeaderError:
                return False
            return bool(tags.getall("APIC"))

        elif suffix in (".ogg", ".opus"):
            from mutagen.oggopus import OggOpus
            from mutagen.oggvorbis import OggVorbis

            loader = OggOpus if suffix == ".opus" else OggVorbis
            audio = loader(file_path)
            return "metadata_block_picture" in (audio.tags or {})

        elif suffix in (".m4a", ".aac", ".mp4"):
            from mutagen.mp4 import MP4

            audio = MP4(file_path)
            return bool(audio.tags and audio.tags.get("covr"))

        elif suffix == ".flac":
            from mutagen.flac import FLAC

            audio = FLAC(file_path)
            return bool(audio.pictures)

        elif suffix == ".wav":
            return False  # WAV not supported

        else:
            # Unknown format: assume no art
            return False

    except Exception as exc:
        logger.warning(f"Could not check cover art for {file_path}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Embedding logic (per format)
# ---------------------------------------------------------------------------


def embed_mp3(file_path: str, img_bytes: bytes) -> None:
    """Embed JPEG cover art into an MP3 file."""
    from mutagen.id3 import APIC, ID3, ID3NoHeaderError

    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.delall("APIC")
    tags.add(
        APIC(
            encoding=3,       # UTF-8
            mime="image/jpeg",
            type=3,           # Cover (front)
            desc="Cover",
            data=img_bytes,
        )
    )
    tags.save(file_path)


def embed_ogg_opus(file_path: str, img_bytes: bytes, suffix: str) -> None:
    """Embed cover art into an Ogg Opus or Ogg Vorbis file."""
    from mutagen.flac import Picture
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis

    loader = OggOpus if suffix == ".opus" else OggVorbis
    audio = loader(file_path)

    pic = Picture()
    pic.type = 3           # Cover (front)
    pic.mime = "image/jpeg"
    pic.desc = "Cover"
    pic.data = img_bytes

    # Encode as FLAC picture block → base64
    pic_data = base64.b64encode(pic.write()).decode("ascii")
    audio["metadata_block_picture"] = [pic_data]
    audio.save()


def embed_m4a(file_path: str, img_bytes: bytes) -> None:
    """Embed JPEG cover art into an M4A/AAC file."""
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(file_path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["covr"] = [MP4Cover(img_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


def embed_flac(file_path: str, img_bytes: bytes) -> None:
    """Embed JPEG cover art into a FLAC file."""
    from mutagen.flac import FLAC, Picture

    audio = FLAC(file_path)
    audio.clear_pictures()

    pic = Picture()
    pic.type = 3
    pic.mime = "image/jpeg"
    pic.desc = "Cover"
    pic.data = img_bytes
    audio.add_picture(pic)
    audio.save()


def embed_artwork(file_path: str, img_bytes: bytes, dry_run: bool) -> bool:
    """
    Embed img_bytes as cover art into file_path using atomic write.

    Returns True on success (or dry_run), False on error or unsupported format.
    """
    suffix = Path(file_path).suffix.lower()

    if suffix == ".wav":
        logger.warning(f"Skipping WAV (no standard tag support): {file_path}")
        return False

    supported = {".mp3", ".ogg", ".opus", ".m4a", ".aac", ".mp4", ".flac"}
    if suffix not in supported:
        logger.warning(f"Unknown format '{suffix}', skipping: {file_path}")
        return False

    if dry_run:
        logger.info(f"[DRY-RUN] Would embed art into: {file_path}")
        return True

    temp_path = file_path + ".tmp"
    try:
        shutil.copy2(file_path, temp_path)

        if suffix == ".mp3":
            embed_mp3(temp_path, img_bytes)
        elif suffix in (".ogg", ".opus"):
            embed_ogg_opus(temp_path, img_bytes, suffix)
        elif suffix in (".m4a", ".aac", ".mp4"):
            embed_m4a(temp_path, img_bytes)
        elif suffix == ".flac":
            embed_flac(temp_path, img_bytes)

        os.replace(temp_path, file_path)
        logger.info(f"Embedded artwork: {file_path}")
        return True

    except Exception as exc:
        logger.exception(f"Failed to embed artwork in {file_path}: {exc}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------


def process_tracks(
    tracks: list[dict],
    access_token: Optional[str],
    conn: sqlite3.Connection,
    dry_run: bool,
) -> dict:
    """Process all candidate tracks and return summary counters."""
    total = len(tracks)
    counters = {
        "already_has_art": 0,
        "embedded": 0,
        "skipped_wav": 0,
        "errors": 0,
        "api_fetches": 0,
    }

    for idx, track in enumerate(tracks, start=1):
        pct = idx / total * 100
        track_id = track["id"]
        local_path = track["local_path"]
        soundcloud_id = track["soundcloud_id"]
        artwork_url = track["artwork_url"]

        suffix = Path(local_path).suffix.lower()

        logger.debug(f"[{idx}/{total} {pct:.1f}%] {local_path}")

        # --- Check file exists ---
        if not os.path.exists(local_path):
            logger.warning(f"File not found, skipping: {local_path}")
            counters["errors"] += 1
            continue

        # --- Skip WAV early ---
        if suffix == ".wav":
            logger.warning(f"Skipping WAV: {local_path}")
            counters["skipped_wav"] += 1
            continue

        # --- Check existing art ---
        if has_embedded_art(local_path):
            logger.debug(f"Already has art, skipping: {local_path}")
            counters["already_has_art"] += 1
            continue

        # --- Resolve artwork URL ---
        fetched_from_api = False
        if not artwork_url:
            if not access_token:
                logger.warning(
                    f"No artwork_url and no access token for id={soundcloud_id}, skipping"
                )
                counters["errors"] += 1
                continue

            logger.info(f"Fetching artwork URL from SC API for id={soundcloud_id}")
            artwork_url = fetch_artwork_url(soundcloud_id, access_token)
            counters["api_fetches"] += 1
            time.sleep(SC_API_DELAY)

            if not artwork_url:
                logger.warning(f"No artwork available for id={soundcloud_id}")
                counters["errors"] += 1
                continue

            fetched_from_api = True

        # --- Upgrade resolution ---
        hq_url = upgrade_artwork_url(artwork_url)

        # --- Download image ---
        img_bytes = download_image(hq_url)
        if not img_bytes:
            # Fall back to original URL in case -large isn't in it
            if hq_url != artwork_url:
                img_bytes = download_image(artwork_url)
            if not img_bytes:
                logger.warning(f"Could not download artwork for {local_path}")
                counters["errors"] += 1
                continue

        # --- Embed ---
        success = embed_artwork(local_path, img_bytes, dry_run)

        if success:
            counters["embedded"] += 1
            # Persist artwork_url to DB if we fetched it from the API
            if fetched_from_api and not dry_run:
                update_artwork_url(conn, track_id, artwork_url)
        elif suffix == ".wav":
            counters["skipped_wav"] += 1
        else:
            counters["errors"] += 1

    return counters


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill SoundCloud artwork into local audio files missing cover art."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually write to audio files (default: dry-run only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N tracks (useful for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Show debug-level log messages",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dry_run = not args.apply

    # Configure loguru
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=log_level, colorize=True)

    if dry_run:
        logger.info("Running in DRY-RUN mode — no files will be modified. Pass --apply to write.")

    # Load SC token (optional — only needed when artwork_url is missing in DB)
    access_token = load_access_token()
    if not access_token:
        logger.warning(
            "No valid SoundCloud token — tracks missing artwork_url will be skipped."
        )

    # Open DB
    db_path = get_db_path()
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        tracks = query_tracks(conn, args.limit)
        logger.info(f"Found {len(tracks)} local tracks with soundcloud_id")

        if not tracks:
            logger.info("Nothing to process.")
            return

        counters = process_tracks(tracks, access_token, conn, dry_run)

        if not dry_run:
            conn.commit()

    finally:
        conn.close()

    # Summary
    total = len(tracks)
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  Total processed    : {total}")
    logger.info(f"  Already had art    : {counters['already_has_art']}")
    logger.info(f"  Embedded           : {counters['embedded']}")
    logger.info(f"  SC API fetches     : {counters['api_fetches']}")
    logger.info(f"  Skipped (WAV)      : {counters['skipped_wav']}")
    logger.info(f"  Errors             : {counters['errors']}")
    if dry_run:
        logger.info("  (DRY-RUN — no files written)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
