"""SoundCloud playlist consolidation script.

Merges ~100 monthly/genre playlists into yearly + curated playlists.
Run with --dry-run (default) to preview, --execute to apply changes.

Usage:
    uv run python scripts/consolidate_playlists.py              # dry run
    uv run python scripts/consolidate_playlists.py --execute    # apply changes
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from functools import partial

# Force unbuffered output
print = partial(print, flush=True)
from pathlib import Path

import requests
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from music_minion.core.database import add_tags, get_db_connection, init_database
from music_minion.domain.library.providers.soundcloud.api import (
    API_BASE_URL,
    _ensure_valid_token,
    _format_playlist_urn,
    create_playlist,
    delete_playlist,
    reorder_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state

# ─── Configuration ──────────────────────────────────────────────────────────

YEARLY_RANGE = range(2016, 2026)

# Monthly playlists to merge into each yearly playlist
MONTHLY_TO_YEARLY: dict[int, list[str]] = {
    2016: [
        "3-22-16", "3/11/2016", "May 2016", "June 2016", "July 2016",
        "December 2016",
    ],
    2017: ["June 17", "July 17"],
    2018: [
        "July 18", "August 18", "September 18", "October 18",
        "November 18", "December 18",
    ],
    2019: [
        "January 2019", "Feb 2019", "Mar 19", "Apr 19", "mix_list_apr_19",
        "May 19", "June 19", "July 19", "September 19", "October 19",
        "Soundcloud - October 19", "Nov 19", "Dec 19",
    ],
    2020: [
        "Jan 20", "Feb 20", "Mar 20", "May 20", "Aug 20",
        "Soundcloud - Aug 20", "September 2020", "October 20",
        "October 2020", "Dec 20", "2020 DNB Mix", "2020 Dub Mix",
    ],
    2021: [
        "Jan 21", "Mar 21", "July 21", "Aug 21", "Sept 21",
        "Oct 21", "Nov 21", "Dec 21", "Other 21",
    ],
    2022: [
        "Jan 22", "Feb 22", "Mar 22", "April 22", "May 22", "June 22",
        "Jul 22", "Sept 22", "September 22", "Oct 22", "Nov 22", "Dec 22",
    ],
    2023: [
        "Jan 23", "Mar 23", "Apr 23", "Jun 23", "Jul 23", "Aug 23",
        "Sept 23", "Oct 23", "Nov 23", "Dec 23",
    ],
    2024: [
        "Jan 24", "Feb 24", "Mar 24", "Apr 24", "May 24", "Jun 24",
        "Jul 24", "Aug 24", "Sept 24", "Oct 24", "Nov 24", "Dec 24",
    ],
    2025: [
        "Jan 25", "Feb 25", "Mar 25", "Apr 25", "May 25", "Jun 25",
        "Jul 25", "Aug 25", "Sept 25", "Oct 25", "Nov 25", "NYE25",
    ],
}

# Genre playlists to merge into BHD
MERGE_INTO_BHD: dict[str, str] = {
    # playlist_name -> genre_tag
    "BassHeadsDelight - DNB": "dnb",
    "BassHeadsDelight - MidTempo": "midtempo",
    "BassHeadsDelight - Wook Shit": "wook",
    "BassHeadsDelight - PsyTrance": "psytrance",
    "BassHeadsDelight - Happy Hardcore": "happy-hardcore",
    "BassHeadsDelight - All Volumes": "bassheadsdelight",
    "BassHeadsDelight - Vol 5": "bassheadsdelight",
    "Bass Heads Delight Vol 4 - Future/Dubstep": "dubstep",
    "Bass Heads Delight Vol 3": "bassheadsdelight",
    "Bass Heads Delight - Vol 6": "bassheadsdelight",
    "Bass Heads Delight - Freeform": "freeform",
    "BHD - VOL 8": "bassheadsdelight",
    "BHD - Vol 9 - Wooks": "wook",
    "BassHeadsDelight Vol 9 - DNB - Pop Remixes": "dnb",
    "EOY - BHD": "bassheadsdelight",
    "EOY - BHD - BH": "bass-house",
    "EOY - BHD - DNB": "dnb",
    "Dubstep Mix": "dubstep",
    "bass house": "bass-house",
    "Bass House Mix": "bass-house",
    "Flux": "bassheadsdelight",
    "DUB": "dubstep",
    "DnB": "dnb",
    "Trap Mix": "trap",
    "Trap": "trap",
    "Rezz(mid-tempo) mix": "midtempo",
}

# Genre playlists to merge into ItsOnTheHouse
MERGE_INTO_IOTH: dict[str, list[str]] = {
    # playlist_name -> [tags]
    "ItsOnTheHouse - Bass House": ["itsonthehouse", "bass-house"],
    "ItsOnTheHouse - Chill": ["itsonthehouse", "chill"],
    "ItsOnTheHouse - Pop Remixes": ["itsonthehouse", "pop-remixes"],
    "Deep House Vocal Mix": ["deep-house", "vocal"],
    "House Mix": ["house"],
}

# Playlists to merge into mixes
MERGE_INTO_MIXES: list[str] = ["Mixes for weekend", "Quaranstream"]

# Event/people playlists to delete (merge tracks to yearly)
DELETE_TO_YEARLY: list[str] = [
    "For Bre", "For Katie", "Jon's Selection", "Jon's party",
    "Jon and Davi requests", "Mdoggy", "Bday", "Boating",
    "Illenium Gorge", "Halloween", "Last minute", "Mug Video",
    "s3rl", "lightcode", "Stoned with Headphones",
    "chill evening maybe sexy", "Emo Night Remixes", "fun mix",
    "pARTy", "Variety", "301", "April",
    # Genre playlists merged to yearly only
    "future/wavy", "New Mix", "BOUNCE", "Chill 100 BPM Mix",
    # Tiny/empty playlists
    "Guest Requests", "Jon and Davi First Dance Songs",
    "deep", "drive", "chiller mix", "DUB_ST_ST_STEP",
    "Soundcloud - Deep/Chill Bass", "Soundcloud - No free download",
    "my mixes", "8-10", "throwback-nye", "Bounce!",
    "2000's throwback", "K-trip",
    # Misc
    "Dec 1", "New Mixes", "Untitled Playlist", "Chiller", "Future",
    # Duplicates
    "wedding", "Wedding",
    # Curation
    "buy", "No free download", "new list", "new deep/chill mix",
]

# Delete locally only (already gone from SC)
LOCAL_ONLY_DELETES: list[str] = ["Not Interested", "Not Quite", "Long Tracks"]

# Playlists to KEEP (never touch)
KEEP_PLAYLISTS: set[str] = {
    "BassHeadsDelight", "ItsOnTheHouse", "mixes",
    "Party Bass", "Deep/Chill Bass", "90's Throwback/Remix",
    "Bre", "artist likes", "reposts", "Release Radar",
    "SoundCloud Likes",
    # 2026 monthly playlists
    "Jan 26", "Feb 26", "Mar 26",
}

# Target playlist DB IDs and SC IDs
BHD_DB_ID = 102
BHD_SC_ID = "1310181712"
IOTH_DB_ID = 104
IOTH_SC_ID = "1309942222"
MIXES_DB_ID = 190
MIXES_SC_ID = "193960384"

MIX_MIN_DURATION_SECS = 600  # 10 minutes


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class PlaylistInfo:
    db_id: int
    name: str
    sc_id: str | None
    track_count: int


@dataclass
class TrackAssignment:
    """A track to be added to a target playlist."""
    sc_track_id: str
    db_track_id: int


@dataclass
class ConsolidationPlan:
    # Phase 1: Yearly playlists to create on SC
    yearly_to_create: list[str] = field(default_factory=list)

    # Phase 2: Monthly tracks merged into yearly {year: [sc_track_ids]}
    yearly_tracks: dict[str, list[str]] = field(default_factory=dict)
    yearly_source_playlists: dict[str, list[str]] = field(default_factory=dict)

    # Phase 3: Genre merge tracks {target_name: [sc_track_ids]}
    bhd_new_tracks: list[str] = field(default_factory=list)
    ioth_new_tracks: list[str] = field(default_factory=list)
    mixes_new_tracks: list[str] = field(default_factory=list)

    # Phase 3b: Tags {db_track_id: [tag_names]}
    tag_assignments: dict[int, list[str]] = field(default_factory=dict)

    # Phase 4: Orphan tracks bucketed by year {year: [sc_track_ids]}
    orphan_yearly: dict[str, list[str]] = field(default_factory=dict)

    # Phase 5: Playlists to delete
    sc_deletes: list[tuple[int, str, str]] = field(default_factory=list)  # (db_id, sc_id, name)
    local_only_deletes: list[tuple[int, str]] = field(default_factory=list)  # (db_id, name)

    # Filled during execution
    created_yearly_sc_ids: dict[str, str] = field(default_factory=dict)

    # Stats
    total_api_calls: int = 0


# ─── Rate Limiter ────────────────────────────────────────────────────────────

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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_local_playlists() -> dict[str, PlaylistInfo]:
    """Load all SC playlists from local DB."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.soundcloud_playlist_id,
                   COUNT(pt.track_id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
            WHERE p.library = 'soundcloud'
            GROUP BY p.id
            """
        ).fetchall()
    return {
        row["name"]: PlaylistInfo(
            db_id=row["id"],
            name=row["name"],
            sc_id=row["soundcloud_playlist_id"],
            track_count=row["track_count"],
        )
        for row in rows
    }


def get_playlist_sc_track_ids(db_playlist_id: int) -> list[str]:
    """Get SC track IDs for a playlist from local DB."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL
            ORDER BY pt.position ASC
            """,
            (db_playlist_id,),
        ).fetchall()
    return [row["soundcloud_id"] for row in rows]


def get_playlist_track_ids_with_db_ids(
    db_playlist_id: int,
) -> list[tuple[str, int]]:
    """Get (sc_track_id, db_track_id) pairs for a playlist."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id, t.id as db_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL
            ORDER BY pt.position ASC
            """,
            (db_playlist_id,),
        ).fetchall()
    return [(row["soundcloud_id"], row["db_id"]) for row in rows]


def get_tracks_in_yearly_playlists() -> set[str]:
    """Get all SC track IDs that are already in any yearly playlist."""
    yearly_names = [str(y) for y in YEARLY_RANGE]
    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(yearly_names))
        rows = conn.execute(
            f"""
            SELECT DISTINCT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            JOIN playlists p ON pt.playlist_id = p.id
            WHERE p.library = 'soundcloud'
              AND p.name IN ({placeholders})
              AND t.soundcloud_id IS NOT NULL
            """,
            yearly_names,
        ).fetchall()
    return {row["soundcloud_id"] for row in rows}


def get_long_tracks_from_playlist(db_playlist_id: int) -> list[str]:
    """Get SC track IDs for tracks >10min in a playlist."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ?
              AND t.soundcloud_id IS NOT NULL
              AND t.duration > ?
            """,
            (db_playlist_id, MIX_MIN_DURATION_SECS),
        ).fetchall()
    return [row["soundcloud_id"] for row in rows]


def fetch_sc_playlist_track_dates(
    state, sc_playlist_id: str
) -> tuple[object, dict[str, int]]:
    """Fetch playlist from SC API with tracks, return {sc_track_id: year}.

    Uses show_tracks=true to get track objects with created_at field.
    """
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, {}

    access_token = token_data["access_token"]
    playlist_urn = _format_playlist_urn(sc_playlist_id)
    url = f"{API_BASE_URL}/playlists/{playlist_urn}"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"show_tracks": True}

    rate_limiter.wait()

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        track_years: dict[str, int] = {}
        for track in data.get("tracks", []):
            if not track:
                continue
            track_id = str(track["id"])
            created_at = track.get("created_at", "")
            if created_at and len(created_at) >= 4:
                try:
                    year = int(created_at[:4])
                    track_years[track_id] = year
                except ValueError:
                    pass
        return state, track_years
    except Exception as e:
        logger.error(f"Error fetching playlist {sc_playlist_id}: {e}")
        return state, {}


# ─── Plan Building ───────────────────────────────────────────────────────────

def build_plan(state, playlists: dict[str, PlaylistInfo]) -> tuple[object, ConsolidationPlan]:
    """Build the full consolidation plan (read-only, no mutations)."""
    plan = ConsolidationPlan()

    # ── Phase 1: Which yearly playlists need to be created? ──
    for year in YEARLY_RANGE:
        year_name = str(year)
        if year_name not in playlists:
            plan.yearly_to_create.append(year_name)

    # ── Phase 2: Merge monthly playlists into yearly ──
    for year, monthly_names in MONTHLY_TO_YEARLY.items():
        year_name = str(year)
        all_sc_ids: list[str] = []
        seen: set[str] = set()
        sources: list[str] = []

        # Start with existing yearly playlist tracks if it exists
        if year_name in playlists:
            existing = get_playlist_sc_track_ids(playlists[year_name].db_id)
            for sc_id in existing:
                if sc_id not in seen:
                    all_sc_ids.append(sc_id)
                    seen.add(sc_id)

        for name in monthly_names:
            if name not in playlists:
                logger.warning(f"Monthly playlist '{name}' not found in DB, skipping")
                continue
            track_ids = get_playlist_sc_track_ids(playlists[name].db_id)
            added = 0
            for sc_id in track_ids:
                if sc_id not in seen:
                    all_sc_ids.append(sc_id)
                    seen.add(sc_id)
                    added += 1
            sources.append(f"{name} ({len(track_ids)} total, {added} new)")

        plan.yearly_tracks[year_name] = all_sc_ids
        plan.yearly_source_playlists[year_name] = sources

    # ── Phase 3: Genre merges ──

    # BHD: collect existing + new tracks
    bhd_existing = set(get_playlist_sc_track_ids(BHD_DB_ID))
    bhd_all = list(bhd_existing)

    for playlist_name, genre_tag in MERGE_INTO_BHD.items():
        if playlist_name not in playlists:
            logger.warning(f"BHD source '{playlist_name}' not found, skipping")
            continue
        tracks = get_playlist_track_ids_with_db_ids(playlists[playlist_name].db_id)
        for sc_id, db_id in tracks:
            # Tag all tracks
            tags = ["bassheadsdelight"]
            if genre_tag != "bassheadsdelight":
                tags.append(genre_tag)
            existing_tags = plan.tag_assignments.get(db_id, [])
            plan.tag_assignments[db_id] = list(set(existing_tags + tags))

            # Add to BHD if not already there
            if sc_id not in bhd_existing:
                bhd_all.append(sc_id)
                bhd_existing.add(sc_id)

    plan.bhd_new_tracks = bhd_all

    # IOTH: collect existing + new tracks
    ioth_existing = set(get_playlist_sc_track_ids(IOTH_DB_ID))
    ioth_all = list(ioth_existing)

    for playlist_name, tags_list in MERGE_INTO_IOTH.items():
        if playlist_name not in playlists:
            logger.warning(f"IOTH source '{playlist_name}' not found, skipping")
            continue
        tracks = get_playlist_track_ids_with_db_ids(playlists[playlist_name].db_id)
        for sc_id, db_id in tracks:
            existing_tags = plan.tag_assignments.get(db_id, [])
            plan.tag_assignments[db_id] = list(set(existing_tags + tags_list))

            if sc_id not in ioth_existing:
                ioth_all.append(sc_id)
                ioth_existing.add(sc_id)

    plan.ioth_new_tracks = ioth_all

    # Mixes: collect existing + new tracks + long tracks from all deleted playlists
    mixes_existing = set(get_playlist_sc_track_ids(MIXES_DB_ID))
    mixes_all = list(mixes_existing)

    for playlist_name in MERGE_INTO_MIXES:
        if playlist_name not in playlists:
            continue
        track_ids = get_playlist_sc_track_ids(playlists[playlist_name].db_id)
        for sc_id in track_ids:
            if sc_id not in mixes_existing:
                mixes_all.append(sc_id)
                mixes_existing.add(sc_id)

    # Collect all playlists being deleted for long track scan
    all_delete_names = (
        list(MERGE_INTO_BHD.keys())
        + list(MERGE_INTO_IOTH.keys())
        + MERGE_INTO_MIXES
        + DELETE_TO_YEARLY
    )
    for year_names in MONTHLY_TO_YEARLY.values():
        all_delete_names.extend(year_names)

    for playlist_name in set(all_delete_names):
        if playlist_name not in playlists:
            continue
        long_tracks = get_long_tracks_from_playlist(playlists[playlist_name].db_id)
        for sc_id in long_tracks:
            if sc_id not in mixes_existing:
                mixes_all.append(sc_id)
                mixes_existing.add(sc_id)

    plan.mixes_new_tracks = mixes_all

    # ── Phase 4: Orphan bucketing ──
    # For every playlist being deleted, ensure all tracks are in a yearly playlist
    # Build set of all tracks already in yearly playlists (after Phase 2 merges)
    yearly_track_set: set[str] = set()
    for year_tracks in plan.yearly_tracks.values():
        yearly_track_set.update(year_tracks)

    # Also include tracks in kept playlists (BHD, IOTH, mixes, etc.)
    # We just need to check: is this track in ANY yearly playlist?
    # Tracks in BHD/IOTH/mixes don't count — they still need yearly placement

    orphan_tracks: dict[str, list[str]] = {}  # Need SC created_at
    playlists_needing_dates: set[str] = set()  # SC playlist IDs to fetch

    for playlist_name in set(all_delete_names + DELETE_TO_YEARLY):
        if playlist_name not in playlists:
            continue
        info = playlists[playlist_name]
        if not info.sc_id:
            continue
        track_ids = get_playlist_sc_track_ids(info.db_id)
        has_orphans = False
        for sc_id in track_ids:
            if sc_id not in yearly_track_set:
                has_orphans = True
                break
        if has_orphans:
            playlists_needing_dates.add(playlist_name)

    # Fetch SC created_at for playlists with orphans
    print(f"\n  Fetching track dates from {len(playlists_needing_dates)} SC playlists...")
    plan.total_api_calls += len(playlists_needing_dates)

    for playlist_name in sorted(playlists_needing_dates):
        info = playlists[playlist_name]
        if not info.sc_id:
            continue
        state, track_years = fetch_sc_playlist_track_dates(state, info.sc_id)
        track_ids = get_playlist_sc_track_ids(info.db_id)

        for sc_id in track_ids:
            if sc_id in yearly_track_set:
                continue  # Already in a yearly playlist
            year = track_years.get(sc_id)
            if year is None or year < 2016:
                continue
            # Redirect 2026+ orphans to Mar 26 (no yearly playlist for current year)
            if year >= 2026:
                year_name = "Mar 26"
            else:
                year_name = str(year)
            if year_name not in plan.orphan_yearly:
                plan.orphan_yearly[year_name] = []
            if sc_id not in yearly_track_set:
                plan.orphan_yearly[year_name].append(sc_id)
                yearly_track_set.add(sc_id)  # Prevent double-adding

    # ── Phase 5: Deletion list ──
    all_to_delete_sc = set()

    # Monthly playlists
    for year_names in MONTHLY_TO_YEARLY.values():
        all_to_delete_sc.update(year_names)

    # Genre merges
    all_to_delete_sc.update(MERGE_INTO_BHD.keys())
    all_to_delete_sc.update(MERGE_INTO_IOTH.keys())
    all_to_delete_sc.update(MERGE_INTO_MIXES)

    # Event/misc playlists
    all_to_delete_sc.update(DELETE_TO_YEARLY)

    for name in sorted(all_to_delete_sc):
        if name not in playlists:
            continue
        info = playlists[name]
        if info.sc_id:
            plan.sc_deletes.append((info.db_id, info.sc_id, name))
        else:
            plan.local_only_deletes.append((info.db_id, name))

    for name in LOCAL_ONLY_DELETES:
        if name in playlists:
            plan.local_only_deletes.append((playlists[name].db_id, name))

    # Count API calls
    plan.total_api_calls += len(plan.yearly_to_create)  # create_playlist
    plan.total_api_calls += len(YEARLY_RANGE)  # reorder yearly
    plan.total_api_calls += 3  # reorder BHD, IOTH, mixes
    plan.total_api_calls += len(plan.sc_deletes)  # delete_playlist

    return state, plan


# ─── Plan Display ────────────────────────────────────────────────────────────

def print_plan(plan: ConsolidationPlan) -> None:
    """Pretty-print the consolidation plan."""
    print("\n" + "=" * 70)
    print("  SoundCloud Playlist Consolidation Plan")
    print("=" * 70)

    # Phase 1
    print(f"\n── Phase 1: Create Yearly Playlists ({len(plan.yearly_to_create)}) ──")
    if plan.yearly_to_create:
        print(f"  CREATE: {', '.join(plan.yearly_to_create)}")
    else:
        print("  All yearly playlists already exist")

    # Phase 2
    print(f"\n── Phase 2: Merge Monthly → Yearly ──")
    for year_name, tracks in sorted(plan.yearly_tracks.items()):
        sources = plan.yearly_source_playlists.get(year_name, [])
        print(f"  {year_name}: {len(tracks)} unique tracks from {len(sources)} playlists")
        for src in sources:
            print(f"    ← {src}")

    # Phase 3
    print(f"\n── Phase 3: Genre Merges ──")
    bhd_existing_count = len(get_playlist_sc_track_ids(BHD_DB_ID))
    print(f"  BassHeadsDelight: {bhd_existing_count} existing + "
          f"{len(plan.bhd_new_tracks) - bhd_existing_count} new = "
          f"{len(plan.bhd_new_tracks)} total")
    ioth_existing_count = len(get_playlist_sc_track_ids(IOTH_DB_ID))
    print(f"  ItsOnTheHouse: {ioth_existing_count} existing + "
          f"{len(plan.ioth_new_tracks) - ioth_existing_count} new = "
          f"{len(plan.ioth_new_tracks)} total")
    mixes_existing_count = len(get_playlist_sc_track_ids(MIXES_DB_ID))
    print(f"  mixes: {mixes_existing_count} existing + "
          f"{len(plan.mixes_new_tracks) - mixes_existing_count} new = "
          f"{len(plan.mixes_new_tracks)} total")
    print(f"  Tags: {len(plan.tag_assignments)} tracks to tag")

    # Phase 4
    print(f"\n── Phase 4: Orphan Track Bucketing ──")
    total_orphans = sum(len(v) for v in plan.orphan_yearly.values())
    if total_orphans:
        for year_name, tracks in sorted(plan.orphan_yearly.items()):
            print(f"  → {year_name}: {len(tracks)} orphan tracks")
    else:
        print("  No orphan tracks found")

    # Phase 5
    print(f"\n── Phase 5: Deletions ──")
    print(f"  SC + Local: {len(plan.sc_deletes)} playlists")
    for _, _, name in sorted(plan.sc_deletes, key=lambda x: x[2]):
        print(f"    ✕ {name}")
    print(f"  Local only: {len(plan.local_only_deletes)} playlists")
    for _, name in plan.local_only_deletes:
        print(f"    ✕ {name} (local only)")

    # Summary
    print(f"\n── Summary ──")
    print(f"  Estimated API calls: {plan.total_api_calls}")
    print(f"  Estimated time: ~{plan.total_api_calls * 2.5 / 60:.1f} minutes")
    print(f"\n  Run with --execute to apply changes.")
    print("=" * 70)


# ─── Execution ───────────────────────────────────────────────────────────────

def execute_plan(state, plan: ConsolidationPlan, playlists: dict[str, PlaylistInfo]) -> None:
    """Execute the consolidation plan against SC API and local DB."""
    checkpoint_path = Path.home() / ".local/share/music-minion/consolidation_checkpoint.json"

    # ── Phase 1: Create yearly playlists ──
    print("\n── Executing Phase 1: Create Yearly Playlists ──")
    for year_name in plan.yearly_to_create:
        rate_limiter.wait()
        state, sc_id, err = create_playlist(state, year_name)
        if err:
            logger.error(f"Failed to create playlist '{year_name}': {err}")
            continue
        print(f"  ✓ Created '{year_name}' (SC ID: {sc_id})")
        plan.created_yearly_sc_ids[year_name] = sc_id

        # Create local DB entry
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO playlists (name, type, library, soundcloud_playlist_id)
                VALUES (?, 'playlist', 'soundcloud', ?)
                """,
                (year_name, sc_id),
            )
            conn.commit()

    # Build mapping of year_name -> sc_playlist_id (existing + newly created)
    yearly_sc_ids: dict[str, str] = {}
    for year in YEARLY_RANGE:
        year_name = str(year)
        if year_name in plan.created_yearly_sc_ids:
            yearly_sc_ids[year_name] = plan.created_yearly_sc_ids[year_name]
        elif year_name in playlists and playlists[year_name].sc_id:
            yearly_sc_ids[year_name] = playlists[year_name].sc_id
        else:
            logger.warning(f"No SC ID for yearly playlist '{year_name}'")

    # ── Phase 2: Sync yearly playlists to SC ──
    print("\n── Executing Phase 2: Sync Yearly Playlists ──")
    for year_name, sc_track_ids in sorted(plan.yearly_tracks.items()):
        if year_name not in yearly_sc_ids:
            continue

        # Add orphan tracks for this year
        orphans = plan.orphan_yearly.get(year_name, [])
        if orphans:
            seen = set(sc_track_ids)
            for sc_id in orphans:
                if sc_id not in seen:
                    sc_track_ids.append(sc_id)
                    seen.add(sc_id)

        rate_limiter.wait()
        state, success, err = reorder_playlist(
            state, yearly_sc_ids[year_name], sc_track_ids
        )
        if success:
            print(f"  ✓ {year_name}: synced {len(sc_track_ids)} tracks")
        else:
            logger.error(f"Failed to sync '{year_name}': {err}")

        # Update local DB playlist_tracks
        _sync_local_playlist_tracks(year_name, sc_track_ids, playlists)

    # Handle orphans assigned to non-yearly playlists (e.g. "Mar 26")
    for orphan_target, orphan_ids in plan.orphan_yearly.items():
        if orphan_target in yearly_sc_ids:
            continue  # Already handled above
        if orphan_target not in playlists or not playlists[orphan_target].sc_id:
            logger.warning(f"No SC ID for orphan target '{orphan_target}', skipping")
            continue
        # Get existing tracks and append orphans
        existing = get_playlist_sc_track_ids(playlists[orphan_target].db_id)
        seen = set(existing)
        merged = list(existing)
        for sc_id in orphan_ids:
            if sc_id not in seen:
                merged.append(sc_id)
                seen.add(sc_id)
        rate_limiter.wait()
        state, success, err = reorder_playlist(
            state, playlists[orphan_target].sc_id, merged
        )
        if success:
            print(f"  ✓ {orphan_target}: added {len(merged) - len(existing)} orphan tracks")
        else:
            logger.error(f"Failed to sync orphans to '{orphan_target}': {err}")
        _sync_local_playlist_tracks(orphan_target, merged, playlists)

    # ── Phase 3: Sync genre target playlists ──
    print("\n── Executing Phase 3: Sync Genre Targets ──")

    for target_name, sc_id, track_list in [
        ("BassHeadsDelight", BHD_SC_ID, plan.bhd_new_tracks),
        ("ItsOnTheHouse", IOTH_SC_ID, plan.ioth_new_tracks),
        ("mixes", MIXES_SC_ID, plan.mixes_new_tracks),
    ]:
        rate_limiter.wait()
        state, success, err = reorder_playlist(state, sc_id, track_list)
        if success:
            print(f"  ✓ {target_name}: synced {len(track_list)} tracks")
        else:
            logger.error(f"Failed to sync '{target_name}': {err}")

    # ── Phase 3b: Apply local tags ──
    print(f"\n── Executing Phase 3b: Tagging {len(plan.tag_assignments)} tracks ──")
    for db_track_id, tags in plan.tag_assignments.items():
        add_tags(db_track_id, tags, source="playlist", confidence=1.0)
    print(f"  ✓ Tagged {len(plan.tag_assignments)} tracks")

    # ── Phase 4: Delete playlists from SC ──
    print(f"\n── Executing Phase 4: Deleting {len(plan.sc_deletes)} SC playlists ──")
    deleted = 0
    failed = 0
    for db_id, sc_id, name in plan.sc_deletes:
        rate_limiter.wait()
        state, success, err = delete_playlist(state, sc_id)
        if success:
            deleted += 1
        else:
            logger.error(f"Failed to delete SC playlist '{name}': {err}")
            failed += 1

        # Delete locally regardless
        _delete_local_playlist(db_id)

    print(f"  ✓ Deleted {deleted} SC playlists ({failed} failed)")

    # ── Phase 5: Delete local-only playlists ──
    print(f"\n── Executing Phase 5: Deleting {len(plan.local_only_deletes)} local playlists ──")
    for db_id, name in plan.local_only_deletes:
        _delete_local_playlist(db_id)
    print(f"  ✓ Deleted {len(plan.local_only_deletes)} local playlists")

    print("\n✓ Consolidation complete!")


def _sync_local_playlist_tracks(
    playlist_name: str,
    sc_track_ids: list[str],
    playlists: dict[str, PlaylistInfo],
) -> None:
    """Update local playlist_tracks to match the SC track list."""
    # Find or get the playlist DB ID
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM playlists WHERE name = ? AND library = 'soundcloud'",
            (playlist_name,),
        ).fetchone()
        if not row:
            return
        playlist_id = row["id"]

        # Clear existing tracks
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )

        # Insert new tracks in order
        for position, sc_id in enumerate(sc_track_ids):
            track_row = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id = ?",
                (sc_id,),
            ).fetchone()
            if track_row:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position)
                    VALUES (?, ?, ?)
                    """,
                    (playlist_id, track_row["id"], position),
                )

        # Update track count
        conn.execute(
            "UPDATE playlists SET track_count = ? WHERE id = ?",
            (len(sc_track_ids), playlist_id),
        )
        conn.commit()


def _delete_local_playlist(db_id: int) -> None:
    """Delete a playlist and its track associations from local DB."""
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ?", (db_id,)
        )
        conn.execute("DELETE FROM playlists WHERE id = ?", (db_id,))
        conn.commit()


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolidate SoundCloud playlists"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Execute the plan (default is dry-run)",
    )
    args = parser.parse_args()

    init_database()

    state = get_web_provider_state()
    if state is None:
        print("ERROR: Not authenticated with SoundCloud. Run music-minion and authenticate first.")
        sys.exit(1)

    print("Loading playlists from local database...")
    playlists = load_local_playlists()
    print(f"  Found {len(playlists)} SoundCloud playlists")

    print("Building consolidation plan...")
    state, plan = build_plan(state, playlists)

    print_plan(plan)

    if not args.execute:
        return

    print("\n" + "!" * 70)
    print("  EXECUTING CONSOLIDATION — THIS WILL MODIFY SOUNDCLOUD PLAYLISTS")
    print("!" * 70)
    confirm = input("\nType 'yes' to proceed: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return

    execute_plan(state, plan, playlists)


if __name__ == "__main__":
    main()
