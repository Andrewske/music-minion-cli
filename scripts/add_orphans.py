"""Add orphan tracks to yearly playlists based on SC created_at.

Orphans = tracks that were in deleted playlists but aren't in any current playlist.
Fetches created_at from SC API, buckets by year, adds to correct yearly playlist.

Usage:
    uv run python scripts/add_orphans.py              # dry run
    uv run python scripts/add_orphans.py --execute    # apply
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
    _format_track_urn,
    _format_playlist_urn,
    reorder_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state

BACKUP_DB = Path.home() / ".local/share/music-minion/music_minion.db.bak"

# Playlists we kept (not deleted)
KEPT_NAMES = [
    "BassHeadsDelight", "ItsOnTheHouse", "mixes",
    "Party Bass", "Deep/Chill Bass", "90's Throwback/Remix",
    "Bre", "artist likes", "reposts", "Release Radar",
    "SoundCloud Likes",
    "Jan 26", "Feb 26", "Mar 26",
]

# Year -> playlist name mapping (for years that were split)
YEAR_TO_PLAYLIST_H1: dict[int, str] = {
    2016: "2016", 2017: "2017", 2018: "2018", 2019: "2019",
    2020: "2020", 2021: "2021", 2022: "2022",
    2023: "2023a", 2024: "2024a", 2025: "2025a",
}
YEAR_TO_PLAYLIST_H2: dict[int, str] = {
    2016: "2016", 2017: "2017", 2018: "2018", 2019: "2019",
    2020: "2020", 2021: "2021", 2022: "2022",
    2023: "2023b", 2024: "2024b", 2025: "2025b",
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


def get_orphan_sc_ids() -> list[str]:
    """Find SC track IDs in deleted playlists (backup) not in any current playlist."""
    backup = sqlite3_mod.connect(str(BACKUP_DB))
    backup.row_factory = sqlite3_mod.Row

    placeholders = ",".join("?" * len(KEPT_NAMES))
    deleted_rows = backup.execute(
        f"""
        SELECT DISTINCT t.soundcloud_id
        FROM playlist_tracks pt
        JOIN tracks t ON pt.track_id = t.id
        JOIN playlists p ON pt.playlist_id = p.id
        WHERE p.library = 'soundcloud'
          AND p.name NOT IN ({placeholders})
          AND t.soundcloud_id IS NOT NULL
        """,
        KEPT_NAMES,
    ).fetchall()
    all_deleted = {r["soundcloud_id"] for r in deleted_rows}
    backup.close()

    with get_db_connection() as conn:
        placed_rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE t.soundcloud_id IS NOT NULL
            """
        ).fetchall()
    placed = {r["soundcloud_id"] for r in placed_rows}

    return list(all_deleted - placed)


def fetch_track_dates(state, sc_track_ids: list[str]) -> tuple:
    """Fetch created_at year and month for tracks from SC API."""
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, {}

    access_token = token_data["access_token"]
    headers = {"Authorization": f"OAuth {access_token}"}

    track_dates: dict[str, tuple[int, int]] = {}  # sc_id -> (year, month)
    chunk_size = 50
    for i in range(0, len(sc_track_ids), chunk_size):
        chunk = sc_track_ids[i : i + chunk_size]
        ids_param = ",".join(chunk)
        rate_limiter.wait()
        try:
            resp = requests.get(
                f"{API_BASE_URL}/tracks",
                headers=headers,
                params={"ids": ids_param},
                timeout=30,
            )
            resp.raise_for_status()
            for track in resp.json():
                if not track:
                    continue
                tid = str(track["id"])
                created = track.get("created_at", "")
                if created and len(created) >= 7:
                    try:
                        year = int(created[:4])
                        month = int(created[5:7])
                        track_dates[tid] = (year, month)
                    except ValueError:
                        pass
            print(f"  Fetched {min(i + chunk_size, len(sc_track_ids))}/{len(sc_track_ids)}...")
        except Exception as e:
            logger.error(f"Error fetching batch at {i}: {e}")

    return state, track_dates


def get_playlist_info() -> dict[str, dict]:
    """Get current playlist name -> {db_id, sc_id, track_count} for yearly playlists."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.soundcloud_playlist_id,
                   COUNT(pt.track_id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
            WHERE p.library = 'soundcloud'
              AND (p.name IN ('2016','2017','2018','2019','2020','2021','2022','Mar 26')
                   OR p.name LIKE '202_a' OR p.name LIKE '202_b')
            GROUP BY p.id
            """
        ).fetchall()
    return {
        r["name"]: {
            "db_id": r["id"],
            "sc_id": r["soundcloud_playlist_id"],
            "count": r["track_count"],
        }
        for r in rows
    }


def get_current_sc_track_ids(db_playlist_id: int) -> list[str]:
    """Get current SC track IDs for a playlist from local DB."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.soundcloud_id FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL
            ORDER BY pt.position ASC
            """,
            (db_playlist_id,),
        ).fetchall()
    return [r["soundcloud_id"] for r in rows]


def sync_local_playlist(playlist_name: str, sc_track_ids: list[str]) -> None:
    """Update local DB playlist_tracks."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM playlists WHERE name = ? AND library = 'soundcloud'",
            (playlist_name,),
        ).fetchone()
        if not row:
            return
        pid = row["id"]
        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (pid,))
        for pos, sc_id in enumerate(sc_track_ids):
            tr = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id = ?", (sc_id,)
            ).fetchone()
            if tr:
                conn.execute(
                    "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                    (pid, tr["id"], pos),
                )
        conn.execute(
            "UPDATE playlists SET track_count = ? WHERE id = ?",
            (len(sc_track_ids), pid),
        )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add orphan tracks to yearly playlists")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    init_database()
    state = get_web_provider_state()
    if state is None:
        print("ERROR: Not authenticated")
        sys.exit(1)

    print("Finding orphan tracks...")
    orphans = get_orphan_sc_ids()
    print(f"  {len(orphans)} orphans found")

    print("\nFetching dates from SC API...")
    state, track_dates = fetch_track_dates(state, orphans)
    print(f"  Got dates for {len(track_dates)}/{len(orphans)} tracks")

    # Get current playlist state
    playlists = get_playlist_info()

    # Bucket orphans into target playlists
    assignments: dict[str, list[str]] = {}  # playlist_name -> [sc_ids to add]
    skipped_no_date = 0
    skipped_old = 0
    skipped_full = 0

    for sc_id in orphans:
        if sc_id not in track_dates:
            skipped_no_date += 1
            continue

        year, month = track_dates[sc_id]

        if year < 2016:
            skipped_old += 1
            continue

        # Map to target playlist
        if year >= 2026:
            target = "Mar 26"
        elif month <= 6:
            target = YEAR_TO_PLAYLIST_H1.get(year, str(year))
        else:
            target = YEAR_TO_PLAYLIST_H2.get(year, str(year))

        if target not in playlists:
            skipped_old += 1
            continue

        current = playlists[target]["count"]
        pending = len(assignments.get(target, []))
        if current + pending >= 500:
            # Try the other half
            if month <= 6:
                alt = YEAR_TO_PLAYLIST_H2.get(year)
            else:
                alt = YEAR_TO_PLAYLIST_H1.get(year)
            if alt and alt in playlists:
                alt_current = playlists[alt]["count"]
                alt_pending = len(assignments.get(alt, []))
                if alt_current + alt_pending < 500:
                    target = alt
                else:
                    skipped_full += 1
                    continue
            else:
                skipped_full += 1
                continue

        if target not in assignments:
            assignments[target] = []
        assignments[target].append(sc_id)

    print(f"\n── Orphan Assignment Plan ──")
    total_assigned = 0
    for name in sorted(assignments.keys()):
        count = len(assignments[name])
        current = playlists[name]["count"]
        total_assigned += count
        print(f"  {name}: +{count} orphans ({current} current → {current + count} total)")

    print(f"\n  Total assigned: {total_assigned}")
    print(f"  Skipped (no SC date / deleted): {skipped_no_date}")
    print(f"  Skipped (before 2016): {skipped_old}")
    print(f"  Skipped (playlist full): {skipped_full}")

    if not args.execute:
        print("\n  Run with --execute to apply.")
        return

    if not args.yes:
        confirm = input("\nType 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

    print("\n── Executing ──")
    for name in sorted(assignments.keys()):
        info = playlists[name]
        new_ids = assignments[name]

        # Get current track list and append
        current_ids = get_current_sc_track_ids(info["db_id"])
        existing_set = set(current_ids)
        merged = list(current_ids)
        for sc_id in new_ids:
            if sc_id not in existing_set:
                merged.append(sc_id)
                existing_set.add(sc_id)

        if len(merged) > 500:
            print(f"  ⚠ {name}: would exceed 500 ({len(merged)}), truncating to 500")
            merged = merged[:500]

        rate_limiter.wait()
        state, success, err = reorder_playlist(state, info["sc_id"], merged)
        if success:
            print(f"  ✓ {name}: {len(merged)} tracks synced (+{len(merged) - len(current_ids)} new)")
            sync_local_playlist(name, merged)
        else:
            print(f"  ✗ {name}: FAILED — {err}")

    print("\n✓ Orphan assignment complete!")


if __name__ == "__main__":
    main()
