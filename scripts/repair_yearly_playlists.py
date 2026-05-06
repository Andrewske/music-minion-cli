"""Repair yearly playlists that exceeded SC's 500-track limit.

Splits 2023/2024/2025 into a/b (Jan-Jun / Jul-Dec) playlists.
Restores track lists from backup DB (pre-consolidation).

Usage:
    uv run python scripts/repair_yearly_playlists.py              # dry run
    uv run python scripts/repair_yearly_playlists.py --execute    # apply
"""

import argparse
import sqlite3 as sqlite3_mod
import sys
import time
from functools import partial
from pathlib import Path

import requests
from loguru import logger

print = partial(print, flush=True)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from music_minion.core.database import get_db_connection, init_database
from music_minion.domain.library.providers.soundcloud.api import (
    API_BASE_URL,
    _ensure_valid_token,
    _format_playlist_urn,
    _format_track_urn,
    create_playlist,
    delete_playlist,
    reorder_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state

BACKUP_DB = Path.home() / ".local/share/music-minion/music_minion.db.bak"

# Existing yearly SC playlist IDs (created but empty/partial)
EXISTING_YEARLY: dict[str, str] = {
    "2020": "2214013187",
    "2023": "2214013235",
    "2024": "2214013253",
    "2025": "2214013274",
}

# Monthly playlists per year from the original consolidation config
MONTHLY_TO_YEARLY: dict[str, list[str]] = {
    "2023": [
        "Jan 23", "Mar 23", "Apr 23", "Jun 23", "Jul 23", "Aug 23",
        "Sept 23", "Oct 23", "Nov 23", "Dec 23",
    ],
    "2024": [
        "Jan 24", "Feb 24", "Mar 24", "Apr 24", "May 24", "Jun 24",
        "Jul 24", "Aug 24", "Sept 24", "Oct 24", "Nov 24", "Dec 24",
    ],
    "2025": [
        "Jan 25", "Feb 25", "Mar 25", "Apr 25", "May 25", "Jun 25",
        "Jul 25", "Aug 25", "Sept 25", "Oct 25", "Nov 25", "NYE25",
    ],
}

# Month number mapping for playlist names
MONTH_PREFIXES: dict[str, int] = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11,
    "Dec": 12, "NYE": 12,
}


class RateLimiter:
    def __init__(self, calls_per_minute: int = 25) -> None:
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()


rate_limiter = RateLimiter()


def get_month_num(playlist_name: str) -> int:
    """Extract month number from playlist name like 'Jan 23' or 'NYE25'."""
    for prefix, num in MONTH_PREFIXES.items():
        if playlist_name.startswith(prefix):
            return num
    return 0


def get_tracks_by_half_from_backup(
    year: str, monthly_names: list[str]
) -> tuple[list[str], list[str]]:
    """Get deduped SC track IDs split into H1 (Jan-Jun) and H2 (Jul-Dec) from backup."""
    conn = sqlite3_mod.connect(str(BACKUP_DB))
    conn.row_factory = sqlite3_mod.Row

    h1_ids: list[str] = []
    h2_ids: list[str] = []
    seen: set[str] = set()

    for playlist_name in monthly_names:
        month = get_month_num(playlist_name)
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            JOIN playlists p ON pt.playlist_id = p.id
            WHERE p.library = 'soundcloud'
              AND p.name = ?
              AND t.soundcloud_id IS NOT NULL
            ORDER BY pt.position ASC
            """,
            (playlist_name,),
        ).fetchall()

        for row in rows:
            sc_id = row["soundcloud_id"]
            if sc_id in seen:
                continue
            seen.add(sc_id)
            if month <= 6:
                h1_ids.append(sc_id)
            else:
                h2_ids.append(sc_id)

    conn.close()
    return h1_ids, h2_ids


def get_tracks_in_yearly_from_current_db() -> set[str]:
    """Get SC track IDs already in yearly playlists in current DB."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            JOIN playlists p ON pt.playlist_id = p.id
            WHERE p.library = 'soundcloud'
              AND (p.name IN ('2016','2017','2018','2019','2020','2021','2022')
                   OR p.name LIKE '202_a' OR p.name LIKE '202_b')
              AND t.soundcloud_id IS NOT NULL
            """
        ).fetchall()
    return {r["soundcloud_id"] for r in rows}


def sync_local_playlist_tracks(playlist_name: str, sc_track_ids: list[str]) -> None:
    """Update local DB playlist_tracks to match."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM playlists WHERE name = ? AND library = 'soundcloud'",
            (playlist_name,),
        ).fetchone()
        if not row:
            return
        playlist_id = row["id"]

        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,)
        )

        for position, sc_id in enumerate(sc_track_ids):
            track_row = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id = ?", (sc_id,)
            ).fetchone()
            if track_row:
                conn.execute(
                    "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                    (playlist_id, track_row["id"], position),
                )

        conn.execute(
            "UPDATE playlists SET track_count = ? WHERE id = ?",
            (len(sc_track_ids), playlist_id),
        )
        conn.commit()


def create_local_playlist(name: str, sc_id: str) -> None:
    """Create a local DB playlist entry."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO playlists (name, type, library, soundcloud_playlist_id)
            VALUES (?, 'playlist', 'soundcloud', ?)
            """,
            (name, sc_id),
        )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair yearly playlists with a/b split")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    init_database()

    if not BACKUP_DB.exists():
        print(f"ERROR: Backup DB not found at {BACKUP_DB}")
        sys.exit(1)

    state = get_web_provider_state()
    if state is None:
        print("ERROR: Not authenticated with SoundCloud")
        sys.exit(1)

    # ── Build plan ──
    print("Reconstructing track lists from backup DB...")
    print(f"Backup: {BACKUP_DB}\n")

    plan: dict[str, dict] = {}  # year -> {h1: [...], h2: [...]}

    for year, monthly_names in MONTHLY_TO_YEARLY.items():
        h1, h2 = get_tracks_by_half_from_backup(year, monthly_names)
        plan[year] = {"h1": h1, "h2": h2}
        print(f"  {year}a (Jan-Jun): {len(h1)} tracks")
        print(f"  {year}b (Jul-Dec): {len(h2)} tracks")
        if len(h1) > 500 or len(h2) > 500:
            print(f"    ⚠ EXCEEDS 500 — needs further splitting!")

    # Steps:
    # 1. Delete existing empty yearly playlists for 2023/2024/2025 on SC
    # 2. Create {year}a and {year}b playlists on SC
    # 3. Push tracks via reorder_playlist (all under 500, single PUT)
    # 4. Sync local DB

    print(f"\n── Plan ──")
    print(f"  Delete on SC: 2023, 2024, 2025 (empty yearly playlists)")
    print(f"  Create on SC: 2023a, 2023b, 2024a, 2024b, 2025a, 2025b")
    api_calls = 3 + 6 + 6  # 3 deletes + 6 creates + 6 reorders
    print(f"  Reorder: 6 playlists (all under 500, single PUT each)")
    print(f"  Estimated API calls: {api_calls}")
    print(f"  Estimated time: ~{api_calls * 2.5 / 60:.1f} minutes")

    if not args.execute:
        print("\n  Run with --execute to apply.")
        return

    if not args.yes:
        confirm = input("\nType 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

    # ── Execute ──

    # Step 1: Delete empty yearly playlists for 2023/2024/2025 on SC + locally
    print("\n── Step 1: Delete empty yearly playlists ──")
    for year in ["2023", "2024", "2025"]:
        sc_id = EXISTING_YEARLY[year]
        rate_limiter.wait()
        state, success, err = delete_playlist(state, sc_id)
        if success:
            print(f"  ✓ Deleted {year} on SC")
        else:
            print(f"  ⚠ Delete {year} on SC: {err}")

        # Delete locally
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id FROM playlists WHERE name = ? AND library = 'soundcloud'",
                (year,),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (row["id"],))
                conn.execute("DELETE FROM playlists WHERE id = ?", (row["id"],))
                conn.commit()
                print(f"  ✓ Deleted {year} locally")

    # Step 2: Create a/b playlists on SC
    print("\n── Step 2: Create a/b playlists ──")
    new_sc_ids: dict[str, str] = {}

    for year in ["2023", "2024", "2025"]:
        for suffix in ["a", "b"]:
            name = f"{year}{suffix}"
            rate_limiter.wait()
            state, sc_id, err = create_playlist(state, name)
            if err:
                print(f"  ✗ Failed to create {name}: {err}")
                continue
            new_sc_ids[name] = sc_id
            create_local_playlist(name, sc_id)
            print(f"  ✓ Created {name} (SC ID: {sc_id})")

    # Step 3: Push tracks
    print("\n── Step 3: Push tracks ──")
    for year in ["2023", "2024", "2025"]:
        for suffix, half_key in [("a", "h1"), ("b", "h2")]:
            name = f"{year}{suffix}"
            if name not in new_sc_ids:
                print(f"  ⚠ Skipping {name} — no SC ID")
                continue

            tracks = plan[year][half_key]
            if not tracks:
                print(f"  {name}: no tracks, skipping")
                continue

            rate_limiter.wait()
            state, success, err = reorder_playlist(state, new_sc_ids[name], tracks)
            if success:
                print(f"  ✓ {name}: {len(tracks)} tracks synced to SC")
                sync_local_playlist_tracks(name, tracks)
                print(f"  ✓ {name}: local DB updated")
            else:
                print(f"  ✗ {name}: FAILED — {err}")

    print("\n✓ Repair complete!")


if __name__ == "__main__":
    main()
