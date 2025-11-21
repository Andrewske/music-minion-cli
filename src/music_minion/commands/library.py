"""
Library management command handlers for Music Minion CLI.

Handles: library, library list, library active, library sync, library auth
"""

from typing import Callable, List, Optional, Tuple

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain.library import providers
from music_minion.domain.library.provider import ProviderConfig

# Removed: old sync_provider_tracks import (replaced with batch_insert_provider_tracks)


def handle_library_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle library management commands.

    Commands:
        library                       # List all libraries
        library list                  # Alias for above
        library active                # Show current active library
        library active <provider>     # Switch to provider
        library sync [provider]       # Sync library from provider (incremental)
        library sync [provider] --full # Full sync (fetch all tracks)
        library auth <provider>       # Authenticate provider

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args or args[0] == "list":
        return handle_library_list(ctx)

    elif args[0] == "active":
        if len(args) == 1:
            return show_active_library(ctx)
        else:
            return switch_active_library(ctx, args[1])

    elif args[0] == "sync":
        # library sync <provider> [likes|playlists] [--full]
        if len(args) < 2:
            log(
                "❌ Usage: library sync <provider> [likes|playlists] [--full]",
                level="error",
            )
            log("Examples:", level="info")
            log(
                "  library sync soundcloud              # Sync tracks + playlists",
                level="info",
            )
            log("  library sync soundcloud likes        # Sync tracks only", level="info")
            log(
                "  library sync soundcloud playlists    # Sync playlists only",
                level="info",
            )
            log(
                "  library sync soundcloud --full       # Full sync (bypass incremental)",
                level="info",
            )
            return ctx, True

        provider = args[1]

        # Parse subcommand (skip --full)
        subcommand = None
        if len(args) > 2 and args[2] != "--full":
            subcommand = args[2]

        full = "--full" in args

        if subcommand == "playlists":
            # Sync playlists only
            if ctx.ui_mode == "blessed" and ctx.update_ui_state:
                return sync_playlists_background(ctx, provider, full=full)
            else:
                return sync_playlists(ctx, provider, full=full)

        elif subcommand == "likes":
            # Sync tracks only (no playlists)
            if ctx.ui_mode == "blessed" and ctx.update_ui_state:
                return sync_library_background(ctx, provider, full=full)
            else:
                return sync_library(ctx, provider, full=full)

        else:
            # No subcommand: sync both tracks and playlists
            log(
                f"🔄 Syncing {provider}: tracks + playlists...",
                level="info",
            )

            # Sync tracks first
            if ctx.ui_mode == "blessed" and ctx.update_ui_state:
                ctx, _ = sync_library_background(ctx, provider, full=full)
                ctx, _ = sync_playlists_background(ctx, provider, full=full)
            else:
                ctx, _ = sync_library(ctx, provider, full=full)
                ctx, _ = sync_playlists(ctx, provider, full=full)

            log(f"✓ Sync complete for {provider}", level="info")
            return ctx, True

    elif args[0] == "auth":
        if len(args) < 2:
            log("❌ Usage: library auth <provider>", level="error")
            return ctx, True
        return authenticate_provider(ctx, args[1])

    else:
        log(f"❌ Unknown library command: {args[0]}", level="error")
        log("Available: list, active, sync, auth", level="info")
        return ctx, True


def handle_library_list(ctx: AppContext) -> Tuple[AppContext, bool]:
    """List all available libraries with track counts.

    Args:
        ctx: Application context

    Returns:
        (ctx, True)
    """
    # Get active library from database
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_provider = row["provider"] if row else "local"

    # Get track counts per provider
    with database.get_db_connection() as conn:
        # Local tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM tracks WHERE local_path IS NOT NULL"
        )
        local_count = cursor.fetchone()["count"]

        # SoundCloud tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM tracks WHERE soundcloud_id IS NOT NULL"
        )
        soundcloud_count = cursor.fetchone()["count"]

        # Spotify tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM tracks WHERE spotify_id IS NOT NULL"
        )
        spotify_count = cursor.fetchone()["count"]

        # YouTube tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM tracks WHERE youtube_id IS NOT NULL"
        )
        youtube_count = cursor.fetchone()["count"]

        # All tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks")
        total_count = cursor.fetchone()["count"]

    log("\n📚 Available Libraries:", level="info")
    log("", level="info")

    # Local
    marker = "●" if active_provider == "local" else " "
    log(f"  {marker} local      ({local_count:,} tracks)", level="info")

    # SoundCloud
    marker = "●" if active_provider == "soundcloud" else " "
    status = "✓" if soundcloud_count > 0 else "⚠"
    log(f"  {marker} soundcloud ({soundcloud_count:,} tracks) {status}", level="info")

    # Spotify (placeholder)
    marker = "●" if active_provider == "spotify" else " "
    log(f"  {marker} spotify    ({spotify_count:,} tracks) ⚠", level="info")

    # All (union)
    marker = "●" if active_provider == "all" else " "
    log(f"  {marker} all        ({total_count:,} tracks)", level="info")

    log("", level="info")
    log(f"Active: {active_provider}", level="info")

    return ctx, True


def show_active_library(ctx: AppContext) -> Tuple[AppContext, bool]:
    """Show currently active library.

    Args:
        ctx: Application context

    Returns:
        (ctx, True)
    """
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_provider = row["provider"] if row else "local"

    log(f"Active library: {active_provider}", level="info")
    return ctx, True


def switch_active_library(ctx: AppContext, provider: str) -> Tuple[AppContext, bool]:
    """Switch to a different library provider.

    Args:
        ctx: Application context
        provider: Provider name ('local', 'soundcloud', 'spotify', 'all')

    Returns:
        (updated_context, True)
    """
    valid_providers = ["local", "soundcloud", "spotify", "youtube", "all"]

    if provider not in valid_providers:
        log(f"❌ Invalid provider: {provider}", level="error")
        log(f"Available: {', '.join(valid_providers, level="info")}")
        return ctx, True

    # Update active library in database
    with database.get_db_connection() as conn:
        conn.execute(
            """
            UPDATE active_library
            SET provider = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """,
            (provider,),
        )
        conn.commit()

    # Reload tracks based on provider
    if provider == "local":
        # Only tracks with local files
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get("local_path")]

    elif provider == "soundcloud":
        # Only tracks with SoundCloud IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get("soundcloud_id")]

    elif provider == "spotify":
        # Only tracks with Spotify IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get("spotify_id")]

    elif provider == "youtube":
        # Only tracks with YouTube IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get("youtube_id")]

    elif provider == "all":
        # All tracks
        filtered = database.get_all_tracks()

    else:
        filtered = []

    # Convert to Track objects
    tracks = [database.db_track_to_library_track(t) for t in filtered]

    # Update context
    ctx = ctx.with_tracks(tracks)

    log(f"✓ Switched to {provider} library ({len(tracks):,} tracks)", level="info")

    return ctx, True


def sync_library(
    ctx: AppContext,
    provider_name: Optional[str] = None,
    full: bool = False,
    progress_callback: Optional[Callable[[str, dict], None]] = None,
) -> Tuple[AppContext, bool]:
    """Sync library from provider.

    Args:
        ctx: Application context
        provider_name: Provider to sync (None = active provider)
        full: If True, do full sync; if False, do incremental sync (default)
        progress_callback: Optional callback for progress updates (event_type, data)

    Returns:
        (updated_context, True)
    """
    # Determine which provider to sync
    if provider_name is None:
        # Get active provider
        with database.get_db_connection() as conn:
            cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
            row = cursor.fetchone()
            provider_name = row["provider"] if row else "local"

    # Validate provider
    if not providers.provider_exists(provider_name):
        log(f"❌ Unknown provider: {provider_name}", level="error")
        return ctx, True

    # Can't sync 'all' - it's a filter, not a provider
    if provider_name == "all":
        log("❌ Cannot sync 'all' - specify a provider", level="error")
        log("❌ Cannot sync 'all' - specify a provider", level="error")
        return ctx, True

    log(f"🔄 Syncing from {provider_name}...", level="info")
    log(f"🔄 Syncing from {provider_name}...", level="info")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state (TODO: load from database in final implementation)
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Check authentication
        if not state.authenticated and provider_name != "local":
            log(f"❌ Not authenticated with {provider_name}", level="error")
            log(f"❌ Not authenticated with {provider_name}", level="error")
            log(f"Run: library auth {provider_name}", level="info")
            return ctx, True

        # Notify init
        if progress_callback:
            progress_callback(
                "init",
                {"provider": provider_name, "mode": "full" if full else "incremental"},
            )

        # Sync library (incremental by default, full if --full flag provided)
        incremental = not full
        new_state, provider_tracks = provider.sync_library(
            state, incremental=incremental
        )

        if not provider_tracks:
            message = f"⚠ No tracks found in {provider_name} library"
            if incremental:
                message += " (incremental mode - all tracks already synced)"
                log(message, level="warning")
                log(message, level="warning")
                log("💡 Tip: Use '--full' flag to re-sync all tracks", level="info")
            else:
                log(message, level="warning")
                log(message, level="warning")
            if progress_callback:
                progress_callback("complete", {"created": 0, "skipped": 0})
            return ctx, True

        # Notify track count
        if progress_callback:
            progress_callback(
                "tracks_fetched",
                {
                    "total": len(provider_tracks),
                    "status": f"Fetched {len(provider_tracks)} tracks",
                },
            )

        # Import to database (no deduplication - creates records with source=provider)
        log(
            f"📥 Importing {len(provider_tracks)} {provider_name} tracks to database...",
            level="info",
        )
        log(f"📥 Importing {len(provider_tracks, level="info")} {provider_name} tracks to database...",
        )

        if progress_callback:
            progress_callback(
                "importing", {"status": f"Importing {len(provider_tracks)} tracks..."}
            )

        from music_minion.domain.library.import_tracks import (
            batch_insert_provider_tracks,
        )

        stats = batch_insert_provider_tracks(provider_tracks, provider_name)

        log(
            f"✓ Import complete! Created: {stats['created']}, Skipped: {stats['skipped']}",
            level="info",
        )
        log("✓ Import complete!", level="info")
        log(f"  Created:  {stats['created']} (new {provider_name} tracks", level="info")
        log(f"  Skipped:  {stats['skipped']} (already synced", level="info")
        log("", level="info")
        log(f"💡 Tip: Run 'library match {provider_name}' to link {provider_name} tracks to local files",
         level="info")

        # Notify completion
        if progress_callback:
            progress_callback(
                "complete", {"created": stats["created"], "skipped": stats["skipped"]}
            )

        # Show playlists for SoundCloud (if configured to sync them)
        if (
            provider_name == "soundcloud"
            and ctx.config.soundcloud.sync_playlists
            and stats["created"] > 0
        ):
            log("", level="info")
            log("📋 Checking SoundCloud playlists...", level="warning")

            new_state2, playlists = provider.get_playlists(new_state)

            if playlists:
                log(f"Found {len(playlists, level="info")} playlists:")
                for i, pl in enumerate(playlists[:5], 1):
                    log(f"  {i}. {pl['name']} ({pl['track_count']} tracks", level="info")

                if len(playlists) > 5:
                    log(f"  ... and {len(playlists, level="info") - 5} more")

                log("", level="info")
                log("💡 Tip: Use 'playlist import soundcloud' to import playlists",
         level="info")

        # Reload tracks if this is the active provider
        with database.get_db_connection() as conn:
            cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
            row = cursor.fetchone()
            active_provider = row["provider"] if row else "local"

        if active_provider == provider_name or active_provider == "all":
            # Reload tracks
            ctx, _ = switch_active_library(ctx, active_provider)

    except Exception as e:
        log(f"❌ Sync failed: {e}", level="error")
        log(f"❌ Sync failed: {e}", level="error")
        if progress_callback:
            progress_callback("error", {"error": str(e)})
        import traceback

        traceback.print_exc()

    return ctx, True


def sync_library_background(
    ctx: AppContext, provider_name: Optional[str] = None, full: bool = False
) -> Tuple[AppContext, bool]:
    """Non-blocking version of sync_library for blessed UI with dashboard progress.

    Args:
        ctx: Application context (must have update_ui_state callback set)
        provider_name: Provider to sync (None = active provider)
        full: If True, do full sync; if False, do incremental sync (default)

    Returns:
        (ctx, True) - Returns immediately, sync runs in background
    """
    import threading
    import uuid

    task_id = str(uuid.uuid4())[:8]

    # Determine provider name first
    if provider_name is None:
        with database.get_db_connection() as conn:
            cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
            row = cursor.fetchone()
            provider_name = row["provider"] if row else "local"

    # Show immediate message in history
    log(
        f"🔄 Starting library sync from {provider_name} in background (task {task_id})",
        level="info",
    )
    log(f"🔄 Starting library sync from {provider_name} in background (task {task_id}", level="info",
    )
    log("", level="info")

    # Get UIState updater from context
    update_ui_state = ctx.update_ui_state
    if not update_ui_state:
        log("❌ Background sync requires blessed UI mode", level="error")
        log("❌ Background sync requires blessed UI mode", level="error")
        return ctx, True

    # Progress callback for thread
    def on_progress(event_type: str, data: dict):
        if event_type == "init":
            update_ui_state(
                {
                    "sync_active": True,
                    "sync_type": "library_sync",
                    "sync_provider": data["provider"],
                    "sync_mode": data["mode"],
                    "sync_current_status": "Initializing...",
                    "sync_task_id": task_id,
                    "sync_stats": {"created": 0, "skipped": 0},
                }
            )

        elif event_type == "tracks_fetched":
            update_ui_state(
                {"sync_total": data["total"], "sync_current_status": data["status"]}
            )

        elif event_type == "importing":
            update_ui_state({"sync_current_status": data["status"]})

        elif event_type == "complete":
            update_ui_state(
                {
                    "sync_active": False,
                    "sync_current_status": "Complete",
                    "sync_stats": {
                        "created": data["created"],
                        "skipped": data["skipped"],
                    },
                    "history_messages": [
                        ("", "white"),
                        (f"✓ Library sync complete! (task {task_id})", "green"),
                        (
                            f"  Created: {data['created']}, Skipped: {data['skipped']}",
                            "green",
                        ),
                        ("", "white"),
                    ],
                }
            )

        elif event_type == "error":
            update_ui_state(
                {
                    "sync_active": False,
                    "sync_current_status": f"❌ Failed: {data['error']}",
                    "history_messages": [
                        ("", "white"),
                        (f"❌ Library sync failed! (task {task_id})", "red"),
                        (f"  Error: {data['error']}", "red"),
                        ("", "white"),
                    ],
                }
            )

    # Background thread
    def run_sync():
        try:
            sync_library(ctx, provider_name, full=full, progress_callback=on_progress)
        except Exception as e:
            update_ui_state(
                {"sync_active": False, "sync_current_status": f"Error: {e}"}
            )
            log(f"❌ Background sync {task_id} failed: {e}", level="error")
            log(f"❌ Background sync {task_id} failed: {e}", level="error")
            import traceback

            traceback.print_exc()

    thread = threading.Thread(
        target=run_sync, daemon=True, name=f"library-sync-{provider_name}-{task_id}"
    )
    thread.start()

    return ctx, True  # Return immediately!


def sync_playlists(
    ctx: AppContext,
    provider_name: str,
    full: bool = False,
    progress_callback: Optional[Callable[[str, dict], None]] = None,
    silent: bool = False,
) -> Tuple[AppContext, bool]:
    """Sync playlists from provider.

    Args:
        ctx: Application context
        provider_name: Provider to sync playlists from
        full: If True, force full re-sync of all playlists
        progress_callback: Optional callback(event_type, data) for progress updates
        silent: If True, suppress all safe_print output (for background mode)

    Returns:
        (updated_context, True)
    """
    from datetime import datetime

    # Helper to call callback safely
    def update_progress(event_type: str, data: dict):
        if progress_callback:
            try:
                progress_callback(event_type, data)
            except Exception:
                # Don't let callback errors crash sync
                pass

    # Helper to print with silent mode check
    def print_if_not_silent(message: str, style: Optional[str] = None):
        if not silent:
            log(message, style=style, level="info")

    # Validate provider
    if not providers.provider_exists(provider_name):
        print_if_not_silent(f"❌ Unknown provider: {provider_name}")
        return ctx, True

    # Can't sync from 'all' or 'local'
    if provider_name in ("all", "local"):
        print_if_not_silent(
            f"❌ Cannot sync playlists from '{provider_name}'"
        )
        return ctx, True

    sync_mode = "full" if full else "incremental"
    log(f"🔄 Syncing playlists from {provider_name} ({sync_mode})...", level="info")
    print_if_not_silent(
        f"🔄 Syncing playlists from {provider_name} ({sync_mode})...",
    )

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Check authentication
        if not state.authenticated:
            log(f"❌ Not authenticated with {provider_name}", level="error")
            print_if_not_silent(
                f"❌ Not authenticated with {provider_name}"
            )
            print_if_not_silent(f"Run: library auth {provider_name}")
            return ctx, True

        # Get playlists from provider
        print_if_not_silent(
            f"📋 Fetching playlists from {provider_name}..."
        )
        state, playlists = provider.get_playlists(state)

        if not playlists:
            log(f"⚠ No playlists found in {provider_name}", level="warning")
            print_if_not_silent(
                f"⚠ No playlists found in {provider_name}"
            )
            return ctx, True

        log(f"✓ Found {len(playlists)} playlists", level="info")
        print_if_not_silent(f"✓ Found {len(playlists)} playlists")
        print_if_not_silent("")

        # Import each playlist

        created_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        total_tracks_added = 0
        failures = []

        # Notify init
        update_progress(
            "init",
            {
                "total": len(playlists),
                "provider": provider_name,
                "mode": "full" if full else "incremental",
            },
        )

        # OPTIMIZATION: Batch lookup all existing playlists before loop
        print_if_not_silent("🔍 Looking up existing playlists...")
        provider_id_field = f"{provider_name}_playlist_id"
        provider_playlist_ids = [pl["id"] for pl in playlists]
        existing_playlists_map = {}

        with database.get_db_connection() as conn:
            if provider_playlist_ids:
                placeholders = ",".join("?" * len(provider_playlist_ids))
                query = f"""
                    SELECT id, name, last_synced_at, provider_last_modified, {provider_id_field}
                    FROM playlists
                    WHERE {provider_id_field} IN ({placeholders})
                """
                cursor = conn.execute(query, provider_playlist_ids)
                existing_playlists_map = {
                    row[provider_id_field]: dict(row) for row in cursor.fetchall()
                }

        print_if_not_silent(
            f"✓ Found {len(existing_playlists_map)} existing playlists"
        )

        # ========================================================================
        # PHASE 1: Collect unique tracks from all playlists needing sync
        # ========================================================================
        print_if_not_silent("\n📦 Collecting tracks from playlists...")

        all_tracks_to_sync = {}  # {soundcloud_id: (soundcloud_id, metadata)}
        playlists_to_sync = []  # [(pl_data, [provider_track_ids])]

        for pl_data in playlists:
            pl_id = pl_data["id"]
            pl_name = pl_data["name"]
            pl_last_modified = pl_data.get("last_modified")

            # Apply incremental sync filter (same logic as current code)
            existing = existing_playlists_map.get(pl_id)
            if existing and not full and pl_last_modified:
                existing_modified = existing["provider_last_modified"]
                if existing_modified and pl_last_modified <= existing_modified:
                    # Skip - no changes since last sync
                    continue

            # Get tracks for this playlist (pre-fetched or fetch individually)
            provider_tracks = None
            if "tracks" in pl_data and pl_data["tracks"]:
                provider_tracks = pl_data["tracks"]
            else:
                # Fall back to individual fetch for large playlists
                state, provider_tracks = provider.get_playlist_tracks(state, pl_id)

            if not provider_tracks:
                continue  # Skip empty playlists

            # Collect unique tracks (deduplicate across playlists)
            track_ids = []
            for track_id, metadata in provider_tracks:
                all_tracks_to_sync[track_id] = (track_id, metadata)
                track_ids.append(track_id)

            playlists_to_sync.append((pl_data, track_ids))

        print_if_not_silent(
            f"✓ Collected {len(all_tracks_to_sync)} unique tracks from {len(playlists_to_sync)} playlists",
        )

        if not playlists_to_sync:
            print_if_not_silent("\n⚠ No playlists need syncing")
            return ctx, True

        # ========================================================================
        # PHASE 2: Batch import missing tracks
        # ========================================================================
        print_if_not_silent("\n🔍 Looking up tracks in database...")

        provider_id_col = f"{provider_name}_id"
        all_provider_ids = list(all_tracks_to_sync.keys())

        # Single batch query for ALL tracks across ALL playlists
        global_track_map = {}  # {provider_id: database_track_id}
        with database.get_db_connection() as conn:
            if all_provider_ids:
                placeholders = ",".join("?" * len(all_provider_ids))
                query = f"SELECT id, {provider_id_col} FROM tracks WHERE {provider_id_col} IN ({placeholders})"
                cursor = conn.execute(query, all_provider_ids)
                global_track_map = {
                    row[provider_id_col]: row["id"] for row in cursor.fetchall()
                }

        existing_count = len(global_track_map)
        missing_count = len(all_tracks_to_sync) - existing_count

        print_if_not_silent(
            f"✓ Found {existing_count}/{len(all_tracks_to_sync)} tracks in database",
        )

        # Import missing tracks using pre-fetched metadata
        if missing_count > 0:
            print_if_not_silent(
                f"📥 Auto-importing {missing_count} missing tracks..."
            )

            missing_provider_ids = [
                pid for pid in all_provider_ids if pid not in global_track_map
            ]
            missing_tracks = [all_tracks_to_sync[pid] for pid in missing_provider_ids]

            # Import using existing batch function
            from music_minion.domain.library.import_tracks import (
                batch_insert_provider_tracks,
            )

            stats = batch_insert_provider_tracks(missing_tracks, provider_name)

            print_if_not_silent(
                f"✓ Imported {stats['created']} new tracks (skipped {stats['skipped']} duplicates)",
            )

            # Re-query to get newly created track IDs
            with database.get_db_connection() as conn:
                placeholders = ",".join("?" * len(missing_provider_ids))
                query = f"SELECT id, {provider_id_col} FROM tracks WHERE {provider_id_col} IN ({placeholders})"
                cursor = conn.execute(query, missing_provider_ids)
                new_tracks = {
                    row[provider_id_col]: row["id"] for row in cursor.fetchall()
                }
                global_track_map.update(new_tracks)

        print_if_not_silent(
            f"✓ Ready to sync {len(playlists_to_sync)} playlists with {len(global_track_map)} tracks",
        )

        # ========================================================================
        # PHASE 3: Update playlist associations using global track map
        # ========================================================================
        print_if_not_silent("\n💾 Updating playlists...")

        # Calculate skipped count (playlists filtered out in PHASE 1)
        skipped_count = len(playlists) - len(playlists_to_sync)

        # OPTIMIZATION: Single transaction for all playlist operations
        with database.get_db_connection() as conn:
            conn.execute("BEGIN")
            try:
                for i, (pl_data, provider_track_ids) in enumerate(playlists_to_sync, 1):
                    pl_name = pl_data["name"]
                    pl_id = pl_data["id"]
                    pl_track_count = pl_data.get("track_count", 0)
                    pl_last_modified = pl_data.get("last_modified")
                    pl_created_at = pl_data.get("created_at")

                    print_if_not_silent(
                        f"\n[{i}/{len(playlists_to_sync)}] Processing: {pl_name}"
                    )

                    # Notify playlist start
                    update_progress(
                        "playlist_start",
                        {"index": i, "name": pl_name, "tracks": pl_track_count},
                    )

                    try:
                        # OPTIMIZATION: Use pre-fetched playlist lookup
                        existing = existing_playlists_map.get(pl_id)

                        # Map provider track IDs to database track IDs using global map
                        track_ids = [
                            global_track_map[pid]
                            for pid in provider_track_ids
                            if pid in global_track_map
                        ]

                        print_if_not_silent(
                            f"  ✓ Mapped {len(track_ids)}/{len(provider_track_ids)} tracks from global map",
                        )

                        # Update existing playlist or create new one
                        if existing:
                            playlist_id = existing["id"]
                            print_if_not_silent(
                                "  💾 Updating existing playlist..."
                            )
                            update_progress(
                                "status_update",
                                {"status": "Updating existing playlist..."},
                            )

                            # Clear existing tracks
                            conn.execute(
                                "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                                (playlist_id,),
                            )

                            # OPTIMIZATION: Batch insert tracks
                            if track_ids:
                                insert_data = [
                                    (playlist_id, track_id, position)
                                    for position, track_id in enumerate(track_ids)
                                ]
                                conn.executemany(
                                    """
                                    INSERT INTO playlist_tracks (playlist_id, track_id, position)
                                    VALUES (?, ?, ?)
                                """,
                                    insert_data,
                                )

                            # Update timestamps and track count
                            conn.execute(
                                """
                                UPDATE playlists
                                SET last_synced_at = ?,
                                    provider_last_modified = ?,
                                    provider_created_at = ?,
                                    track_count = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """,
                                (
                                    datetime.now().isoformat(),
                                    pl_last_modified,
                                    pl_created_at,
                                    len(track_ids),
                                    playlist_id,
                                ),
                            )

                            print_if_not_silent(
                                f"  ✅ Updated '{pl_name}' with {len(track_ids)} tracks",
                            )
                            updated_count += 1
                            update_progress(
                                "playlist_complete",
                                {
                                    "result": "updated",
                                    "tracks_added": len(track_ids),
                                    "stats": {
                                        "created": created_count,
                                        "updated": updated_count,
                                        "skipped": skipped_count,
                                        "failed": failed_count,
                                    },
                                },
                            )

                        else:
                            # Ensure unique playlist name (handle duplicates)
                            final_name = pl_name
                            cursor = conn.execute(
                                "SELECT id FROM playlists WHERE name = ?", (pl_name,)
                            )
                            if cursor.fetchone():
                                final_name = f"{provider_name.title()} - {pl_name}"
                                print_if_not_silent(
                                    f"  ℹ Renamed to '{final_name}' (name collision)",
                                )

                            print_if_not_silent(
                                "  💾 Creating playlist..."
                            )
                            update_progress(
                                "status_update", {"status": "Creating playlist..."}
                            )

                            # Create playlist in database (inline to use same transaction)
                            cursor = conn.execute(
                                """
                                INSERT INTO playlists (name, type, description, track_count, created_at, updated_at)
                                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """,
                                (
                                    final_name,
                                    "manual",
                                    pl_data.get("description"),
                                    len(track_ids),
                                ),
                            )
                            playlist_id = cursor.lastrowid

                            # Set provider playlist ID and timestamps
                            conn.execute(
                                f"""
                                UPDATE playlists
                                SET {provider_id_field} = ?,
                                    last_synced_at = ?,
                                    provider_last_modified = ?,
                                    provider_created_at = ?
                                WHERE id = ?
                            """,
                                (
                                    pl_id,
                                    datetime.now().isoformat(),
                                    pl_last_modified,
                                    pl_created_at,
                                    playlist_id,
                                ),
                            )

                            # OPTIMIZATION: Batch insert tracks
                            if track_ids:
                                insert_data = [
                                    (playlist_id, track_id, position)
                                    for position, track_id in enumerate(track_ids)
                                ]
                                conn.executemany(
                                    """
                                    INSERT INTO playlist_tracks (playlist_id, track_id, position)
                                    VALUES (?, ?, ?)
                                """,
                                    insert_data,
                                )

                            print_if_not_silent(
                                f"  ✅ Created '{final_name}' with {len(track_ids)} tracks",
                            )
                            created_count += 1
                            update_progress(
                                "playlist_complete",
                                {
                                    "result": "created",
                                    "tracks_added": len(track_ids),
                                    "stats": {
                                        "created": created_count,
                                        "updated": updated_count,
                                        "skipped": skipped_count,
                                        "failed": failed_count,
                                    },
                                },
                            )

                        total_tracks_added += len(track_ids)

                    except Exception as e:
                        print_if_not_silent(f"  ❌ Failed: {e}")
                        failures.append((pl_name, str(e)))
                        failed_count += 1
                        update_progress(
                            "playlist_complete",
                            {
                                "result": "failed",
                                "tracks_added": 0,
                                "stats": {
                                    "created": created_count,
                                    "updated": updated_count,
                                    "skipped": skipped_count,
                                    "failed": failed_count,
                                },
                            },
                        )
                        continue

                # OPTIMIZATION: Single commit for all playlists
                conn.commit()
                print_if_not_silent(
                    "\n✓ Committed all playlist changes to database"
                )

            except Exception as e:
                conn.rollback()
                log(f"❌ Transaction failed, rolled back: {e}", level="error")
                print_if_not_silent(
                    f"❌ Transaction failed, rolled back: {e}"
                )
                raise

        # Notify complete
        update_progress(
            "complete",
            {
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "total_tracks": total_tracks_added,
            },
        )

        # Summary
        print_if_not_silent("")
        print_if_not_silent("=" * 50)
        print_if_not_silent("✓ Playlist sync complete!")
        print_if_not_silent(f"  Created:  {created_count} playlists")
        print_if_not_silent(f"  Updated:  {updated_count} playlists")
        print_if_not_silent(f"  Skipped:  {skipped_count} (unchanged)")
        print_if_not_silent(f"  Failed:   {failed_count} playlists")
        print_if_not_silent(f"  Tracks:   {total_tracks_added} total tracks added")
        print_if_not_silent("")

        # Report failures
        if failures:
            print_if_not_silent("⚠ Failed playlists:")
            for name, error in failures:
                print_if_not_silent(f"  - {name}: {error}")
            print_if_not_silent("")

        if created_count > 0:
            print_if_not_silent(
                f"💡 Tip: Switch to {provider_name} library to view these playlists",
            )
            print_if_not_silent(f"    library active {provider_name}")
            print_if_not_silent("")
            print_if_not_silent(
                f"💡 To link {provider_name} tracks to local files, run:"
            )
            print_if_not_silent(f"    library match {provider_name}")

    except Exception as e:
        log(f"❌ Playlist sync failed: {e}", level="error")
        print_if_not_silent(f"❌ Playlist sync failed: {e}")
        if progress_callback:
            progress_callback("error", {"error": str(e)})
        import traceback

        traceback.print_exc()

    return ctx, True


def sync_playlists_background(
    ctx: AppContext, provider_name: str, full: bool = False
) -> Tuple[AppContext, bool]:
    """Non-blocking version of sync_playlists for blessed UI with dashboard progress.

    Args:
        ctx: Application context (must have update_ui_state callback set)
        provider_name: Provider to sync playlists from
        full: If True, force full re-sync of all playlists

    Returns:
        (ctx, True) - Returns immediately, sync runs in background
    """
    import threading
    import uuid

    task_id = str(uuid.uuid4())[:8]

    # Show immediate message in history
    log(
        f"🔄 Starting playlist sync from {provider_name} in background (task {task_id})",
        level="info",
    )
    log(f"🔄 Starting playlist sync from {provider_name} in background (task {task_id}", level="info",
    )
    log("", level="info")

    # Get UIState updater from context
    update_ui_state = ctx.update_ui_state
    if not update_ui_state:
        log("❌ Background sync requires blessed UI mode", level="error")
        log("❌ Background sync requires blessed UI mode", level="error")
        return ctx, True

    # Progress callback for thread
    def on_progress(event_type: str, data: dict):
        if event_type == "init":
            update_ui_state(
                {
                    "sync_active": True,
                    "sync_type": "playlist_sync",
                    "sync_provider": data["provider"],
                    "sync_mode": data["mode"],
                    "sync_total": data["total"],
                    "sync_progress": 0,
                    "sync_current_name": "",
                    "sync_current_status": "Initializing...",
                    "sync_task_id": task_id,
                    "sync_stats": {
                        "created": 0,
                        "updated": 0,
                        "skipped": 0,
                        "failed": 0,
                    },
                }
            )

        elif event_type == "playlist_start":
            update_ui_state(
                {
                    "sync_progress": data["index"],
                    "sync_current_name": data["name"],
                    "sync_current_status": f"Processing ({data['tracks']} tracks)",
                }
            )

        elif event_type == "status_update":
            update_ui_state({"sync_current_status": data["status"]})

        elif event_type == "playlist_complete":
            # Update stats
            update_ui_state({"sync_stats": data["stats"]})

        elif event_type == "complete":
            update_ui_state(
                {
                    "sync_active": False,
                    "sync_current_status": "Complete",
                    "history_messages": [
                        ("", "white"),
                        (f"✓ Playlist sync complete! (task {task_id})", "green"),
                        (
                            f"  Created: {data['created']}, Updated: {data['updated']}, Skipped: {data['skipped']}, Failed: {data['failed']}",
                            "green",
                        ),
                        (f"  Total tracks: {data.get('total_tracks', 0)}", "green"),
                        ("", "white"),
                    ],
                }
            )

        elif event_type == "error":
            update_ui_state(
                {
                    "sync_active": False,
                    "sync_current_status": f"❌ Failed: {data['error']}",
                    "history_messages": [
                        ("", "white"),
                        (f"❌ Playlist sync failed! (task {task_id})", "red"),
                        (f"  Error: {data['error']}", "red"),
                        ("", "white"),
                    ],
                }
            )

    # Background thread
    def run_sync():
        try:
            sync_playlists(
                ctx,
                provider_name,
                full=full,
                progress_callback=on_progress,
                silent=True,
            )
        except Exception as e:
            update_ui_state(
                {"sync_active": False, "sync_current_status": f"Error: {e}"}
            )
            log(f"❌ Background sync {task_id} failed: {e}", level="error")
            log(f"❌ Background sync {task_id} failed: {e}", level="error")
            import traceback

            traceback.print_exc()

    thread = threading.Thread(
        target=run_sync, daemon=True, name=f"playlist-sync-{provider_name}-{task_id}"
    )
    thread.start()

    return ctx, True  # Return immediately!


def authenticate_provider(
    ctx: AppContext, provider_name: str
) -> Tuple[AppContext, bool]:
    """Authenticate with a provider.

    Args:
        ctx: Application context
        provider_name: Provider to authenticate

    Returns:
        (ctx, True)
    """
    # Validate provider
    if not providers.provider_exists(provider_name):
        log(f"❌ Unknown provider: {provider_name}", level="error")
        return ctx, True

    # Local provider doesn't need auth
    if provider_name == "local":
        log("✓ Local provider doesn't require authentication", level="info")
        return ctx, True

    log(f"🔐 Authenticating with {provider_name}...", level="info")
    log(f"🔐 Authenticating with {provider_name}...", level="info")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Inject provider config into state cache for OAuth flow
        if provider_name == "soundcloud":
            config_dict = {
                "client_id": ctx.config.soundcloud.client_id,
                "client_secret": ctx.config.soundcloud.client_secret,
                "redirect_uri": ctx.config.soundcloud.redirect_uri,
            }
            state = state.with_cache(config=config_dict)

        # Authenticate
        new_state, success = provider.authenticate(state)

        if success:
            log(f"✓ Successfully authenticated with {provider_name}!", level="info")
            log(f"✓ Successfully authenticated with {provider_name}!",
         level="info")

            # Save auth state to database
            auth_data = new_state.cache.get("token_data", {})
            config_data = new_state.cache.get("config", {})
            database.save_provider_state(provider_name, auth_data, config_data)

        else:
            log("❌ Authentication failed", level="error")
            log("❌ Authentication failed", level="error")

    except Exception as e:
        log(f"❌ Authentication error: {e}", level="error")
        log(f"❌ Authentication error: {e}", level="error")

    return ctx, True
