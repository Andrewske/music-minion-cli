"""SoundCloud Discovery Reposts Sync Engine.

Fetches reposts from ranked artists, selects tracks via quality-weighted
round-robin, and updates SoundCloud playlists.
"""

import time
from datetime import datetime, timezone
from typing import Any, Callable, NamedTuple, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    get_user_reposts,
    reorder_playlist,
)
from web.backend.queries import discovery as discovery_queries
from web.backend.soundcloud_auth import get_web_provider_state


class DiscoverySyncResult(NamedTuple):
    tracks_fetched: int
    tracks_new: int
    tracks_added_to_playlist: int
    mixes_added: int
    artists_checked: int
    errors: list[str]
    dry_run: bool


def prepare_for_sync(playlist_id: int) -> tuple[int, list[int]]:
    """Prepare for sync by processing any active organizer session.

    If an organizer session is active for this playlist:
    1. Count unassigned tracks (these stay in the playlist)
    2. Process bucket assignments — linked bucket tracks → 'liked', unlinked → 'dismissed'
    3. Return (remaining_slots, kept_track_ids) where remaining_slots = 100 - unassigned_count

    If no active session:
    Returns (100, []) — full replacement
    """
    target = 100

    with get_db_connection() as conn:
        session = conn.execute(
            "SELECT id FROM bucket_sessions WHERE playlist_id = ? AND status = 'active'",
            (playlist_id,),
        ).fetchone()

        if not session:
            return target, []

        session_id = session["id"]

        buckets = conn.execute(
            """SELECT b.id, b.name, bpl.playlist_id as linked_playlist_id
            FROM buckets b
            LEFT JOIN bucket_playlist_links bpl ON bpl.bucket_id = b.id
            WHERE b.session_id = ?""",
            (session_id,),
        ).fetchall()

        liked_sc_ids: list[str] = []
        dismissed_sc_ids: list[str] = []

        for bucket in buckets:
            bucket_tracks = conn.execute(
                """SELECT t.soundcloud_id FROM bucket_tracks bt
                JOIN tracks t ON t.id = bt.track_id
                WHERE bt.bucket_id = ? AND t.soundcloud_id IS NOT NULL""",
                (bucket["id"],),
            ).fetchall()

            sc_ids = [row["soundcloud_id"] for row in bucket_tracks]

            if bucket["linked_playlist_id"]:
                liked_sc_ids.extend(sc_ids)
            else:
                dismissed_sc_ids.extend(sc_ids)

        if liked_sc_ids:
            discovery_queries.mark_tracks_liked(liked_sc_ids)
        if dismissed_sc_ids:
            discovery_queries.mark_tracks_dismissed(dismissed_sc_ids)

        if liked_sc_ids or dismissed_sc_ids:
            discovery_queries.recalculate_artist_stats()

        unassigned = conn.execute(
            """SELECT pt.track_id FROM playlist_tracks pt
            WHERE pt.playlist_id = ?
            AND pt.track_id NOT IN (
                SELECT bt.track_id FROM bucket_tracks bt
                JOIN buckets b ON b.id = bt.bucket_id
                WHERE b.session_id = ?
            )""",
            (playlist_id, session_id),
        ).fetchall()

        kept_track_ids = [row["track_id"] for row in unassigned]
        remaining_slots = max(0, target - len(kept_track_ids))

        logger.info(
            f"Partial refill: {len(liked_sc_ids)} liked, {len(dismissed_sc_ids)} dismissed, "
            f"{len(kept_track_ids)} kept, {remaining_slots} slots to fill"
        )

        return remaining_slots, kept_track_ids


def _fetch_all_reposts(
    state: Any,
    artists: list[dict[str, Any]],
    seen_ids: set[str],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[Any, dict[int, list[dict[str, Any]]], list[str]]:
    """Fetch reposts from all ranked artists.

    Args:
        state: SC provider state
        artists: ranked artist dicts with 'id', 'soundcloud_user_id', 'slug', etc.
        seen_ids: set of SC track IDs already seen (for dedup)
        progress_callback: optional fn(message, current, total) for progress updates

    Returns:
        (updated_state, {artist_id: [track_dicts]}, errors_list)
    """
    artist_tracks: dict[int, list[dict[str, Any]]] = {}
    errors: list[str] = []
    total = len(artists)

    for i, artist in enumerate(artists):
        if progress_callback:
            progress_callback(
                f"Checking {artist['slug']} ({i + 1}/{total})",
                i + 1,
                total,
            )

        sc_user_id = artist["soundcloud_user_id"]
        artist_id = artist["id"]
        retries = 0
        backoff = 2

        while retries <= 3:
            try:
                state, reposts, api_error = get_user_reposts(state, sc_user_id)
                if api_error:
                    if "Rate limited" in api_error:
                        raise Exception(api_error)  # Trigger retry logic
                    logger.warning(f"API error for {artist['slug']}: {api_error}")
                    errors.append(f"{artist['slug']}: {api_error}")
                    break
                unseen = [
                    t for t in reposts
                    if str(t.get("id", "")) not in seen_ids
                ]
                artist_tracks[artist_id] = unseen
                discovery_queries.update_artist_last_checked(artist_id, len(unseen))
                break
            except Exception as exc:
                err_str = str(exc)
                is_rate_limit = "429" in err_str or "rate limit" in err_str.lower()

                if is_rate_limit and retries < 3:
                    retries += 1
                    logger.warning(
                        f"Rate limited fetching reposts for {artist['slug']}, "
                        f"retry {retries}/3 after {backoff}s"
                    )
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    msg = f"Failed to fetch reposts for {artist['slug']}: {exc}"
                    logger.exception(msg)
                    errors.append(msg)
                    break

        if i < total - 1:
            time.sleep(0.2)

    return state, artist_tracks, errors


def _select_tracks_chronological(
    all_tracks: list[dict[str, Any]],
    slot_caps: dict[int, int],
    target_count: int = 100,
) -> list[dict[str, Any]]:
    """Select tracks by recency with per-artist slot caps.

    Sorts all tracks by created_at descending (newest first), then walks
    the list taking each track unless that artist has hit their cap.
    Stops at target_count.

    Each track dict must have an 'artist_id' key (added during fetch).
    """
    def _parse_created_at(track: dict[str, Any]) -> str:
        return track.get("created_at", "1970/01/01 00:00:00 +0000")

    sorted_tracks = sorted(all_tracks, key=_parse_created_at, reverse=True)

    counts: dict[int, int] = {}
    selected: list[dict[str, Any]] = []

    for track in sorted_tracks:
        if len(selected) >= target_count:
            break
        artist_id = track.get("artist_id")
        if artist_id is None:
            continue
        cap = slot_caps.get(artist_id, 1)
        current = counts.get(artist_id, 0)
        if current < cap:
            selected.append(track)
            counts[artist_id] = current + 1

    return selected


def _split_by_duration(
    tracks: list[dict[str, Any]],
    threshold_ms: int = 600_000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split tracks into short (≤ threshold) and mixes (> threshold)."""
    short: list[dict[str, Any]] = []
    mixes: list[dict[str, Any]] = []

    for track in tracks:
        duration = track.get("duration", 0) or 0
        if duration > threshold_ms:
            mixes.append(track)
        else:
            short.append(track)

    return short, mixes


def _sync_tracks_to_local_db(
    tracks: list[dict[str, Any]],
    playlist_id: int,
    replace: bool = True,
    position_offset: int = 0,
) -> int:
    """Import SC tracks to local tracks table and update playlist_tracks.

    Args:
        tracks: list of SC API track dicts
        playlist_id: local playlist ID
        replace: if True, clear playlist_tracks first; if False, append
        position_offset: starting position for new tracks

    Returns count of tracks synced.
    """
    if not tracks:
        return 0

    with get_db_connection() as conn:
        if replace:
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            )

        synced = 0
        for idx, track in enumerate(tracks):
            sc_id = str(track["id"])
            title = track.get("title", "")
            artist = track.get("user", {}).get("username", "Unknown")
            duration_sec = (track.get("duration", 0) or 0) / 1000.0

            conn.execute(
                """INSERT OR IGNORE INTO tracks
                    (title, artist, duration, soundcloud_id, source)
                VALUES (?, ?, ?, ?, 'soundcloud')""",
                (title, artist, duration_sec, sc_id),
            )

            row = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id = ?",
                (sc_id,),
            ).fetchone()

            if not row:
                logger.warning(f"Could not find local track after insert: sc_id={sc_id}")
                continue

            local_id = row["id"]
            position = position_offset + idx

            conn.execute(
                """INSERT OR REPLACE INTO playlist_tracks (playlist_id, track_id, position)
                VALUES (?, ?, ?)""",
                (playlist_id, local_id, position),
            )

            # Update discovery_tracks with local_track_id
            conn.execute(
                "UPDATE discovery_tracks SET local_track_id = ? WHERE soundcloud_id = ?",
                (local_id, sc_id),
            )

            synced += 1

        # Update playlist track_count
        conn.execute(
            """UPDATE playlists SET track_count = (
                SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?
            ) WHERE id = ?""",
            (playlist_id, playlist_id),
        )

        conn.commit()

    return synced


def _push_to_sc_playlist(
    state: Any,
    sc_playlist_id: str,
    track_sc_ids: list[str],
    replace: bool = True,
) -> tuple[Any, bool, Optional[str]]:
    """Push tracks to a SoundCloud playlist.

    If replace: use reorder_playlist() to replace all tracks.
    If not replace: use add_track_to_playlist() for each track (append).
    """
    if replace:
        state, success, err = reorder_playlist(state, sc_playlist_id, track_sc_ids)
        return state, success, err

    errors: list[str] = []
    for sc_track_id in track_sc_ids:
        state, success, err = add_track_to_playlist(state, sc_playlist_id, sc_track_id)
        if not success:
            errors.append(f"track {sc_track_id}: {err}")

    if errors:
        return state, False, "; ".join(errors)
    return state, True, None


def run_discovery_sync(
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> DiscoverySyncResult:
    """Run the full discovery sync cycle.

    Steps:
    1. Get SC auth
    2. Get discovery playlist IDs
    3. prepare_for_sync() — handle active session, get remaining_slots and kept_track_ids
    4. Load ranked artists + compute slot caps
    5. Load seen track IDs for dedup
    6. Fetch reposts from all artists
    7. Store new tracks + reposters in DB
    8. Split by duration (short vs mixes)
    9. Round-robin select from short tracks
    10. If not dry_run: push to SC playlists and sync to local DB
    11. Log sync run
    """
    started_at = datetime.now(timezone.utc)
    errors: list[str] = []

    state = get_web_provider_state()
    if state is None:
        raise RuntimeError("SoundCloud not authenticated — cannot run discovery sync")

    reposts_playlist_id = discovery_queries.get_discovery_playlist_id("soundcloud_reposts")
    if reposts_playlist_id is None:
        raise RuntimeError("No discovery playlist configured (discovery_source='soundcloud_reposts')")

    mixes_playlist_id = discovery_queries.get_mixes_playlist_id()

    # Resolve SC playlist IDs
    with get_db_connection() as conn:
        reposts_row = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (reposts_playlist_id,),
        ).fetchone()
        sc_reposts_playlist_id: Optional[str] = (
            reposts_row["soundcloud_playlist_id"] if reposts_row else None
        )

        sc_mixes_playlist_id: Optional[str] = None
        if mixes_playlist_id:
            mixes_row = conn.execute(
                "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
                (mixes_playlist_id,),
            ).fetchone()
            sc_mixes_playlist_id = mixes_row["soundcloud_playlist_id"] if mixes_row else None

    # Step 3: Handle active organizer session
    remaining_slots, kept_track_ids = prepare_for_sync(reposts_playlist_id)
    is_partial = len(kept_track_ids) > 0
    target_count = remaining_slots

    # Step 4: Load ranked artists + compute slot caps
    artists = discovery_queries.get_ranked_artists()
    if not artists:
        logger.warning("No resolved artists found — nothing to fetch")

    slot_caps = discovery_queries.compute_slot_caps(artists)

    # Step 5: Load seen track IDs
    seen_ids = discovery_queries.get_seen_track_ids()

    # Step 6: Fetch reposts
    if progress_callback:
        progress_callback("Fetching artist reposts...", 0, len(artists))

    state, artist_tracks, fetch_errors = _fetch_all_reposts(
        state, artists, seen_ids, progress_callback
    )
    errors.extend(fetch_errors)

    # Flatten all fetched tracks for storage
    all_fetched: list[dict[str, Any]] = []
    for artist_id, tracks in artist_tracks.items():
        for track in tracks:
            all_fetched.append({**track, "artist_id": artist_id})

    tracks_fetched = len(all_fetched)
    artists_checked = len(artist_tracks)

    # Step 7: Store new tracks in discovery_tracks
    discovery_records = [
        {
            "soundcloud_id": str(t["id"]),
            "slug": t.get("permalink", ""),
            "title": t.get("title", ""),
            "artist_name": t.get("user", {}).get("username", "Unknown"),
            "duration_ms": t.get("duration", 0) or 0,
        }
        for t in all_fetched
    ]
    tracks_new = discovery_queries.insert_discovery_tracks(discovery_records)

    # Store track-reposter relationships
    if all_fetched:
        sc_ids_fetched = [str(t["id"]) for t in all_fetched]
        sc_id_to_discovery_id = discovery_queries.get_discovery_track_ids_by_sc_ids(sc_ids_fetched)

        reposter_links: list[tuple[int, int, Optional[str]]] = []
        for track in all_fetched:
            sc_id = str(track["id"])
            discovery_track_id = sc_id_to_discovery_id.get(sc_id)
            if discovery_track_id is None:
                continue
            artist_id = track.get("artist_id")
            if artist_id is None:
                continue
            reposter_links.append((discovery_track_id, artist_id, None))

        discovery_queries.insert_track_reposters(reposter_links)

    # Step 8: Split by duration
    short_tracks, mix_tracks = _split_by_duration(all_fetched)

    # Step 9: Select tracks chronologically with per-artist caps
    if progress_callback:
        progress_callback("Selecting tracks...", artists_checked, artists_checked)

    selected_short = _select_tracks_chronological(
        short_tracks, slot_caps, target_count
    )
    selected_sc_ids = [str(t["id"]) for t in selected_short]

    # Select mixes (up to a reasonable cap, no round-robin needed)
    selected_mixes = mix_tracks[:20] if mix_tracks else []
    selected_mix_sc_ids = [str(t["id"]) for t in selected_mixes]

    tracks_added = len(selected_short)
    mixes_added = len(selected_mixes)

    # Mark selected tracks in discovery_tracks
    batch_number = discovery_queries.get_next_batch_number()
    if selected_sc_ids:
        discovery_queries.mark_tracks_in_playlist(selected_sc_ids, batch_number)
    if selected_mix_sc_ids:
        discovery_queries.mark_tracks_in_playlist(selected_mix_sc_ids, batch_number)

    logger.info(
        f"Discovery sync: {tracks_fetched} fetched, {tracks_new} new, "
        f"{tracks_added} selected for playlist, {mixes_added} mixes"
    )

    # Step 10: Push to SC playlists and sync to local DB
    if not dry_run:
        if selected_short and sc_reposts_playlist_id:
            # Partial refill: new tracks at beginning, kept tracks shift down
            # Local DB: new tracks at 0..N, kept tracks already exist starting at N
            synced = _sync_tracks_to_local_db(
                selected_short,
                reposts_playlist_id,
                replace=not is_partial,
                position_offset=0,
            )
            logger.info(f"Synced {synced} tracks to local reposts playlist")

            # For SC: combine new sc IDs + kept SC IDs (kept tracks need SC IDs looked up)
            if is_partial:
                with get_db_connection() as conn:
                    kept_sc_ids_rows = conn.execute(
                        f"""SELECT t.soundcloud_id FROM tracks t
                        WHERE t.id IN ({','.join('?' * len(kept_track_ids))})
                        AND t.soundcloud_id IS NOT NULL""",
                        kept_track_ids,
                    ).fetchall()
                kept_sc_ids = [r["soundcloud_id"] for r in kept_sc_ids_rows]
                full_sc_ids = selected_sc_ids + kept_sc_ids
            else:
                full_sc_ids = selected_sc_ids

            state, success, err = _push_to_sc_playlist(
                state, sc_reposts_playlist_id, full_sc_ids, replace=True
            )
            if success:
                logger.info(f"Pushed {len(full_sc_ids)} tracks to SC reposts playlist")
            else:
                msg = f"SC reposts playlist push failed: {err}"
                logger.warning(msg)
                errors.append(msg)

        if selected_mixes and mixes_playlist_id and sc_mixes_playlist_id:
            synced_mixes = _sync_tracks_to_local_db(
                selected_mixes,
                mixes_playlist_id,
                replace=True,
                position_offset=0,
            )
            logger.info(f"Synced {synced_mixes} mixes to local mixes playlist")

            state, success, err = _push_to_sc_playlist(
                state, sc_mixes_playlist_id, selected_mix_sc_ids, replace=True
            )
            if success:
                logger.info(f"Pushed {len(selected_mix_sc_ids)} tracks to SC mixes playlist")
            else:
                msg = f"SC mixes playlist push failed: {err}"
                logger.warning(msg)
                errors.append(msg)

    # Step 11: Log sync run
    duration_sec = (datetime.now(timezone.utc) - started_at).total_seconds()
    discovery_queries.log_sync_run(
        started_at=started_at,
        artists_checked=artists_checked,
        tracks_fetched=tracks_fetched,
        tracks_added=tracks_added,
        mixes_added=mixes_added,
        tracks_skipped=tracks_fetched - tracks_added - mixes_added,
        dry_run=dry_run,
        duration_seconds=duration_sec,
    )

    return DiscoverySyncResult(
        tracks_fetched=tracks_fetched,
        tracks_new=tracks_new,
        tracks_added_to_playlist=tracks_added,
        mixes_added=mixes_added,
        artists_checked=artists_checked,
        errors=errors,
        dry_run=dry_run,
    )
