"""
Library management command handlers for Music Minion CLI.

Handles: library, library list, library active, library sync, library auth
"""

from typing import List, Tuple, Optional, Callable
from pathlib import Path

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.domain.library import providers
from music_minion.domain.library.provider import ProviderConfig, ProviderState
# Removed: old sync_provider_tracks import (replaced with batch_insert_provider_tracks)


def safe_print(ctx: AppContext, message: str, style: Optional[str] = None) -> None:
    """Print using Rich Console if available."""
    if ctx.console:
        if style:
            ctx.console.print(message, style=style)
        else:
            ctx.console.print(message)
    else:
        print(message)


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
        # Check if syncing playlists
        if len(args) > 1 and args[1] == "playlists":
            # library sync playlists <provider>
            if len(args) < 3:
                safe_print(ctx, "❌ Usage: library sync playlists <provider>", style="bold red")
                safe_print(ctx, "Example: library sync playlists soundcloud")
                return ctx, True
            # Parse provider and --full flag
            provider = None
            full = False
            for arg in args[2:]:
                if arg == "--full":
                    full = True
                else:
                    provider = arg
            if not provider:
                safe_print(ctx, "❌ Usage: library sync playlists <provider> [--full]", style="bold red")
                safe_print(ctx, "Example: library sync playlists soundcloud")
                return ctx, True

            # Route to background or blocking version based on UI mode
            if ctx.ui_mode == 'blessed' and ctx.update_ui_state:
                return sync_playlists_background(ctx, provider, full=full)
            else:
                return sync_playlists(ctx, provider, full=full)
        else:
            # library sync <provider> [--full]
            provider = None
            full = False
            for arg in args[1:]:
                if arg == "--full":
                    full = True
                else:
                    provider = arg

            # Route to background or blocking version based on UI mode
            if ctx.ui_mode == 'blessed' and ctx.update_ui_state:
                return sync_library_background(ctx, provider, full=full)
            else:
                return sync_library(ctx, provider, full=full)

    elif args[0] == "auth":
        if len(args) < 2:
            safe_print(ctx, "❌ Usage: library auth <provider>", style="bold red")
            return ctx, True
        return authenticate_provider(ctx, args[1])

    else:
        safe_print(ctx, f"❌ Unknown library command: {args[0]}", style="bold red")
        safe_print(ctx, "Available: list, active, sync, auth")
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
        active_provider = row['provider'] if row else 'local'

    # Get track counts per provider
    with database.get_db_connection() as conn:
        # Local tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks WHERE local_path IS NOT NULL")
        local_count = cursor.fetchone()['count']

        # SoundCloud tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks WHERE soundcloud_id IS NOT NULL")
        soundcloud_count = cursor.fetchone()['count']

        # Spotify tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks WHERE spotify_id IS NOT NULL")
        spotify_count = cursor.fetchone()['count']

        # YouTube tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks WHERE youtube_id IS NOT NULL")
        youtube_count = cursor.fetchone()['count']

        # All tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks")
        total_count = cursor.fetchone()['count']

    safe_print(ctx, "\n📚 Available Libraries:", style="bold cyan")
    safe_print(ctx, "")

    # Local
    marker = "●" if active_provider == "local" else " "
    safe_print(ctx, f"  {marker} local      ({local_count:,} tracks)")

    # SoundCloud
    marker = "●" if active_provider == "soundcloud" else " "
    status = "✓" if soundcloud_count > 0 else "⚠"
    safe_print(ctx, f"  {marker} soundcloud ({soundcloud_count:,} tracks) {status}")

    # Spotify (placeholder)
    marker = "●" if active_provider == "spotify" else " "
    safe_print(ctx, f"  {marker} spotify    ({spotify_count:,} tracks) ⚠")

    # All (union)
    marker = "●" if active_provider == "all" else " "
    safe_print(ctx, f"  {marker} all        ({total_count:,} tracks)")

    safe_print(ctx, "")
    safe_print(ctx, f"Active: {active_provider}", style="dim")

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
        active_provider = row['provider'] if row else 'local'

    safe_print(ctx, f"Active library: {active_provider}", style="bold cyan")
    return ctx, True


def switch_active_library(ctx: AppContext, provider: str) -> Tuple[AppContext, bool]:
    """Switch to a different library provider.

    Args:
        ctx: Application context
        provider: Provider name ('local', 'soundcloud', 'spotify', 'all')

    Returns:
        (updated_context, True)
    """
    valid_providers = ['local', 'soundcloud', 'spotify', 'youtube', 'all']

    if provider not in valid_providers:
        safe_print(ctx, f"❌ Invalid provider: {provider}", style="bold red")
        safe_print(ctx, f"Available: {', '.join(valid_providers)}")
        return ctx, True

    # Update active library in database
    with database.get_db_connection() as conn:
        conn.execute("""
            UPDATE active_library
            SET provider = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (provider,))
        conn.commit()

    # Reload tracks based on provider
    if provider == 'local':
        # Only tracks with local files
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get('local_path')]

    elif provider == 'soundcloud':
        # Only tracks with SoundCloud IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get('soundcloud_id')]

    elif provider == 'spotify':
        # Only tracks with Spotify IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get('spotify_id')]

    elif provider == 'youtube':
        # Only tracks with YouTube IDs
        db_tracks = database.get_all_tracks()
        filtered = [t for t in db_tracks if t.get('youtube_id')]

    elif provider == 'all':
        # All tracks
        filtered = database.get_all_tracks()

    else:
        filtered = []

    # Convert to Track objects
    from music_minion.domain.library.models import Track
    tracks = [database.db_track_to_library_track(t) for t in filtered]

    # Update context
    ctx = ctx.with_tracks(tracks)

    safe_print(ctx, f"✓ Switched to {provider} library ({len(tracks):,} tracks)", style="bold green")

    return ctx, True


def sync_library(
    ctx: AppContext,
    provider_name: Optional[str] = None,
    full: bool = False,
    progress_callback: Optional[Callable[[str, dict], None]] = None
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
            provider_name = row['provider'] if row else 'local'

    # Validate provider
    if not providers.provider_exists(provider_name):
        safe_print(ctx, f"❌ Unknown provider: {provider_name}", style="bold red")
        return ctx, True

    # Can't sync 'all' - it's a filter, not a provider
    if provider_name == 'all':
        safe_print(ctx, "❌ Cannot sync 'all' - specify a provider", style="bold red")
        return ctx, True

    safe_print(ctx, f"🔄 Syncing from {provider_name}...", style="bold yellow")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state (TODO: load from database in final implementation)
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Check authentication
        if not state.authenticated and provider_name != 'local':
            safe_print(ctx, f"❌ Not authenticated with {provider_name}", style="bold red")
            safe_print(ctx, f"Run: library auth {provider_name}")
            return ctx, True

        # Notify init
        if progress_callback:
            progress_callback("init", {
                "provider": provider_name,
                "mode": "full" if full else "incremental"
            })

        # Sync library (incremental by default, full if --full flag provided)
        incremental = not full
        new_state, provider_tracks = provider.sync_library(state, incremental=incremental)

        if not provider_tracks:
            safe_print(ctx, f"⚠ No tracks found in {provider_name} library", style="yellow")
            if progress_callback:
                progress_callback("complete", {"created": 0, "skipped": 0})
            return ctx, True

        # Notify track count
        if progress_callback:
            progress_callback("tracks_fetched", {
                "total": len(provider_tracks),
                "status": f"Fetched {len(provider_tracks)} tracks"
            })

        # Import to database (no deduplication - creates records with source=provider)
        safe_print(ctx, f"📥 Importing {len(provider_tracks)} {provider_name} tracks to database...")

        if progress_callback:
            progress_callback("importing", {
                "status": f"Importing {len(provider_tracks)} tracks..."
            })

        from music_minion.domain.library.import_tracks import batch_insert_provider_tracks

        stats = batch_insert_provider_tracks(provider_tracks, provider_name)

        safe_print(ctx, f"✓ Import complete!", style="bold green")
        safe_print(ctx, f"  Created:  {stats['created']} (new {provider_name} tracks)")
        safe_print(ctx, f"  Skipped:  {stats['skipped']} (already synced)")
        safe_print(ctx, "")
        safe_print(ctx, f"💡 Tip: Run 'library match {provider_name}' to link {provider_name} tracks to local files", style="dim")

        # Notify completion
        if progress_callback:
            progress_callback("complete", {
                "created": stats['created'],
                "skipped": stats['skipped']
            })

        # Show playlists for SoundCloud (if configured to sync them)
        if provider_name == 'soundcloud' and ctx.config.soundcloud.sync_playlists and stats['created'] > 0:
            safe_print(ctx, "")
            safe_print(ctx, "📋 Checking SoundCloud playlists...", style="yellow")

            new_state2, playlists = provider.get_playlists(new_state)

            if playlists:
                safe_print(ctx, f"Found {len(playlists)} playlists:")
                for i, pl in enumerate(playlists[:5], 1):
                    safe_print(ctx, f"  {i}. {pl['name']} ({pl['track_count']} tracks)")

                if len(playlists) > 5:
                    safe_print(ctx, f"  ... and {len(playlists) - 5} more")

                safe_print(ctx, "")
                safe_print(ctx, "💡 Tip: Use 'playlist import soundcloud' to import playlists", style="dim")

        # Reload tracks if this is the active provider
        with database.get_db_connection() as conn:
            cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
            row = cursor.fetchone()
            active_provider = row['provider'] if row else 'local'

        if active_provider == provider_name or active_provider == 'all':
            # Reload tracks
            ctx, _ = switch_active_library(ctx, active_provider)

    except Exception as e:
        safe_print(ctx, f"❌ Sync failed: {e}", style="bold red")

    return ctx, True


def sync_library_background(
    ctx: AppContext,
    provider_name: Optional[str] = None,
    full: bool = False
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
            provider_name = row['provider'] if row else 'local'

    # Show immediate message in history
    safe_print(ctx, f"🔄 Starting library sync from {provider_name} in background (task {task_id})", style="bold yellow")
    safe_print(ctx, "Watch the dashboard for live progress updates", style="dim")
    safe_print(ctx, "")

    # Get UIState updater from context
    update_ui_state = ctx.update_ui_state
    if not update_ui_state:
        safe_print(ctx, "❌ Background sync requires blessed UI mode", style="bold red")
        return ctx, True

    # Progress callback for thread
    def on_progress(event_type: str, data: dict):
        if event_type == "init":
            update_ui_state({
                "sync_active": True,
                "sync_type": "library_sync",
                "sync_provider": data["provider"],
                "sync_mode": data["mode"],
                "sync_current_status": "Initializing...",
                "sync_task_id": task_id,
                "sync_stats": {"created": 0, "skipped": 0}
            })

        elif event_type == "tracks_fetched":
            update_ui_state({
                "sync_total": data["total"],
                "sync_current_status": data["status"]
            })

        elif event_type == "importing":
            update_ui_state({"sync_current_status": data["status"]})

        elif event_type == "complete":
            update_ui_state({
                "sync_active": False,
                "sync_current_status": "Complete",
                "sync_stats": {"created": data["created"], "skipped": data["skipped"]},
                "history_messages": [
                    ("", "white"),
                    (f"✓ Library sync complete! (task {task_id})", "green"),
                    (f"  Created: {data['created']}, Skipped: {data['skipped']}", "green"),
                    ("", "white")
                ]
            })

    # Background thread
    def run_sync():
        try:
            sync_library(ctx, provider_name, full=full, progress_callback=on_progress)
        except Exception as e:
            update_ui_state({
                "sync_active": False,
                "sync_current_status": f"Error: {e}"
            })
            safe_print(ctx, f"❌ Background sync {task_id} failed: {e}", style="bold red")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(
        target=run_sync,
        daemon=True,
        name=f"library-sync-{provider_name}-{task_id}"
    )
    thread.start()

    return ctx, True  # Return immediately!


def sync_playlists(
    ctx: AppContext,
    provider_name: str,
    full: bool = False,
    progress_callback: Optional[Callable[[str, dict], None]] = None,
    silent: bool = False
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
            except Exception as e:
                # Don't let callback errors crash sync
                pass

    # Helper to print with silent mode check
    def print_if_not_silent(message: str, style: Optional[str] = None):
        if not silent:
            safe_print(ctx, message, style=style)

    # Validate provider
    if not providers.provider_exists(provider_name):
        print_if_not_silent(f"❌ Unknown provider: {provider_name}", style="bold red")
        return ctx, True

    # Can't sync from 'all' or 'local'
    if provider_name in ('all', 'local'):
        print_if_not_silent(f"❌ Cannot sync playlists from '{provider_name}'", style="bold red")
        return ctx, True

    sync_mode = "full" if full else "incremental"
    print_if_not_silent(f"🔄 Syncing playlists from {provider_name} ({sync_mode})...", style="bold yellow")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Check authentication
        if not state.authenticated:
            print_if_not_silent(f"❌ Not authenticated with {provider_name}", style="bold red")
            print_if_not_silent(f"Run: library auth {provider_name}")
            return ctx, True

        # Get playlists from provider
        print_if_not_silent(f"📋 Fetching playlists from {provider_name}...", style="yellow")
        state, playlists = provider.get_playlists(state)

        if not playlists:
            print_if_not_silent(f"⚠ No playlists found in {provider_name}", style="yellow")
            return ctx, True

        print_if_not_silent(f"✓ Found {len(playlists)} playlists", style="green")
        print_if_not_silent("")

        # Import each playlist
        from music_minion.domain import playlists as playlist_crud

        created_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        total_tracks_added = 0
        failures = []

        # Notify init
        update_progress("init", {
            "total": len(playlists),
            "provider": provider_name,
            "mode": "full" if full else "incremental"
        })

        # OPTIMIZATION: Batch lookup all existing playlists before loop
        print_if_not_silent(f"🔍 Looking up existing playlists...", style="yellow")
        provider_id_field = f"{provider_name}_playlist_id"
        provider_playlist_ids = [pl['id'] for pl in playlists]
        existing_playlists_map = {}

        with database.get_db_connection() as conn:
            if provider_playlist_ids:
                placeholders = ','.join('?' * len(provider_playlist_ids))
                query = f"""
                    SELECT id, name, last_synced_at, provider_last_modified, {provider_id_field}
                    FROM playlists
                    WHERE {provider_id_field} IN ({placeholders})
                """
                cursor = conn.execute(query, provider_playlist_ids)
                existing_playlists_map = {
                    row[provider_id_field]: dict(row)
                    for row in cursor.fetchall()
                }

        print_if_not_silent(f"✓ Found {len(existing_playlists_map)} existing playlists", style="green")

        # OPTIMIZATION: Single transaction for all playlist operations
        with database.get_db_connection() as conn:
            conn.execute("BEGIN")
            try:
                for i, pl_data in enumerate(playlists, 1):
                    pl_name = pl_data['name']
                    pl_id = pl_data['id']
                    pl_track_count = pl_data.get('track_count', 0)
                    pl_last_modified = pl_data.get('last_modified')
                    pl_created_at = pl_data.get('created_at')

                    print_if_not_silent(f"\n[{i}/{len(playlists)}] Processing: {pl_name}")
                    print_if_not_silent(f"  Tracks: {pl_track_count}")

                    # Notify playlist start
                    update_progress("playlist_start", {
                        "index": i,
                        "name": pl_name,
                        "tracks": pl_track_count
                    })

                    try:
                        # OPTIMIZATION: Use pre-fetched playlist lookup
                        existing = existing_playlists_map.get(pl_id)

                        # Incremental sync: Skip if not modified and not full sync
                        if existing and not full and pl_last_modified:
                            existing_modified = existing['provider_last_modified']
                            if existing_modified and pl_last_modified <= existing_modified:
                                print_if_not_silent(f"  ⏭ Skipped (no changes since {existing_modified})", style="dim")
                                skipped_count += 1
                                continue

                        # Get playlist tracks (use pre-fetched if available, otherwise fetch individually)
                        if "tracks" in pl_data and pl_data["tracks"]:
                            # Tracks were pre-fetched in get_playlists() call
                            print_if_not_silent(f"  ✓ Using pre-fetched tracks ({len(pl_data['tracks'])} tracks)", style="dim")
                            provider_tracks = pl_data["tracks"]
                        else:
                            # Fall back to individual fetch (large playlists or old provider implementations)
                            print_if_not_silent(f"  📥 Fetching tracks from {provider_name}...", style="yellow")
                            update_progress("status_update", {"status": f"Fetching tracks from {provider_name}..."})
                            state, provider_tracks = provider.get_playlist_tracks(state, pl_id)

                        if not provider_tracks:
                            print_if_not_silent(f"  ⚠ No tracks found", style="yellow")
                            skipped_count += 1
                            continue

                        # Batch lookup tracks in database by provider ID
                        print_if_not_silent(f"  🔍 Looking up {len(provider_tracks)} tracks in database...")
                        update_progress("status_update", {"status": f"Looking up {len(provider_tracks)} tracks in database..."})

                        provider_id_col = f"{provider_name}_id"
                        provider_ids = [track_id for track_id, _ in provider_tracks]

                        # Single batch query with IN clause (using outer transaction connection)
                        placeholders = ','.join('?' * len(provider_ids))
                        query = f"SELECT id, {provider_id_col} FROM tracks WHERE {provider_id_col} IN ({placeholders})"
                        cursor = conn.execute(query, provider_ids)

                        # Build lookup dict
                        id_map = {row[provider_id_col]: row['id'] for row in cursor.fetchall()}

                        # Map provider IDs to database track IDs in order
                        track_ids = [id_map[pid] for pid in provider_ids if pid in id_map]

                        found_pct = (len(track_ids) / len(provider_tracks) * 100) if provider_tracks else 0
                        print_if_not_silent(f"  ✓ Found {len(track_ids)}/{len(provider_tracks)} tracks ({found_pct:.0f}%)", style="green")

                        if len(track_ids) < len(provider_tracks):
                            missing = len(provider_tracks) - len(track_ids)
                            print_if_not_silent(f"  ⚠ {missing} tracks not found (run 'library sync {provider_name}' first)", style="yellow")

                        # Update existing playlist or create new one
                        if existing:
                            playlist_id = existing['id']
                            print_if_not_silent(f"  💾 Updating existing playlist...", style="yellow")
                            update_progress("status_update", {"status": "Updating existing playlist..."})

                            # Clear existing tracks
                            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

                            # OPTIMIZATION: Batch insert tracks
                            if track_ids:
                                insert_data = [
                                    (playlist_id, track_id, position)
                                    for position, track_id in enumerate(track_ids)
                                ]
                                conn.executemany("""
                                    INSERT INTO playlist_tracks (playlist_id, track_id, position)
                                    VALUES (?, ?, ?)
                                """, insert_data)

                            # Update timestamps and track count
                            conn.execute("""
                                UPDATE playlists
                                SET last_synced_at = ?,
                                    provider_last_modified = ?,
                                    provider_created_at = ?,
                                    track_count = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (datetime.now().isoformat(), pl_last_modified, pl_created_at, len(track_ids), playlist_id))

                            print_if_not_silent(f"  ✅ Updated '{pl_name}' with {len(track_ids)} tracks", style="bold green")
                            updated_count += 1
                            update_progress("playlist_complete", {
                                "result": "updated",
                                "tracks_added": len(track_ids),
                                "stats": {"created": created_count, "updated": updated_count, "skipped": skipped_count, "failed": failed_count}
                            })

                        else:
                            # Ensure unique playlist name (handle duplicates)
                            final_name = pl_name
                            cursor = conn.execute("SELECT id FROM playlists WHERE name = ?", (pl_name,))
                            if cursor.fetchone():
                                final_name = f"{provider_name.title()} - {pl_name}"
                                print_if_not_silent(f"  ℹ Renamed to '{final_name}' (name collision)", style="cyan")

                            print_if_not_silent(f"  💾 Creating playlist...", style="yellow")
                            update_progress("status_update", {"status": "Creating playlist..."})

                            # Create playlist in database (inline to use same transaction)
                            cursor = conn.execute("""
                                INSERT INTO playlists (name, type, description, track_count, created_at, updated_at)
                                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """, (final_name, 'manual', pl_data.get('description'), len(track_ids)))
                            playlist_id = cursor.lastrowid

                            # Set provider playlist ID and timestamps
                            conn.execute(f"""
                                UPDATE playlists
                                SET {provider_id_field} = ?,
                                    last_synced_at = ?,
                                    provider_last_modified = ?,
                                    provider_created_at = ?
                                WHERE id = ?
                            """, (pl_id, datetime.now().isoformat(), pl_last_modified, pl_created_at, playlist_id))

                            # OPTIMIZATION: Batch insert tracks
                            if track_ids:
                                insert_data = [
                                    (playlist_id, track_id, position)
                                    for position, track_id in enumerate(track_ids)
                                ]
                                conn.executemany("""
                                    INSERT INTO playlist_tracks (playlist_id, track_id, position)
                                    VALUES (?, ?, ?)
                                """, insert_data)

                            print_if_not_silent(f"  ✅ Created '{final_name}' with {len(track_ids)} tracks", style="bold green")
                            created_count += 1
                            update_progress("playlist_complete", {
                                "result": "created",
                                "tracks_added": len(track_ids),
                                "stats": {"created": created_count, "updated": updated_count, "skipped": skipped_count, "failed": failed_count}
                            })

                        total_tracks_added += len(track_ids)

                    except Exception as e:
                        print_if_not_silent(f"  ❌ Failed: {e}", style="bold red")
                        failures.append((pl_name, str(e)))
                        failed_count += 1
                        update_progress("playlist_complete", {
                            "result": "failed",
                            "tracks_added": 0,
                            "stats": {"created": created_count, "updated": updated_count, "skipped": skipped_count, "failed": failed_count}
                        })
                        continue

                # OPTIMIZATION: Single commit for all playlists
                conn.commit()
                print_if_not_silent(f"\n✓ Committed all playlist changes to database", style="green")

            except Exception as e:
                conn.rollback()
                print_if_not_silent(f"❌ Transaction failed, rolled back: {e}", style="bold red")
                raise

        # Notify complete
        update_progress("complete", {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "total_tracks": total_tracks_added
        })

        # Summary
        print_if_not_silent("")
        print_if_not_silent("=" * 50)
        print_if_not_silent(f"✓ Playlist sync complete!", style="bold green")
        print_if_not_silent(f"  Created:  {created_count} playlists")
        print_if_not_silent(f"  Updated:  {updated_count} playlists")
        print_if_not_silent(f"  Skipped:  {skipped_count} (unchanged)")
        print_if_not_silent(f"  Failed:   {failed_count} playlists")
        print_if_not_silent(f"  Tracks:   {total_tracks_added} total tracks added")
        print_if_not_silent("")

        # Report failures
        if failures:
            print_if_not_silent("⚠ Failed playlists:", style="yellow")
            for name, error in failures:
                print_if_not_silent(f"  - {name}: {error}", style="yellow")
            print_if_not_silent("")

        if created_count > 0:
            print_if_not_silent(f"💡 Tip: Switch to {provider_name} library to view these playlists", style="dim")
            print_if_not_silent(f"    library active {provider_name}", style="dim")
            print_if_not_silent("")
            print_if_not_silent(f"💡 To link {provider_name} tracks to local files, run:", style="dim")
            print_if_not_silent(f"    library match {provider_name}", style="dim")

    except Exception as e:
        print_if_not_silent(f"❌ Playlist sync failed: {e}", style="bold red")
        import traceback
        traceback.print_exc()

    return ctx, True


def sync_playlists_background(ctx: AppContext, provider_name: str, full: bool = False) -> Tuple[AppContext, bool]:
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
    safe_print(ctx, f"🔄 Starting playlist sync from {provider_name} in background (task {task_id})", style="bold yellow")
    safe_print(ctx, "Watch the dashboard for live progress updates", style="dim")
    safe_print(ctx, "")

    # Get UIState updater from context
    update_ui_state = ctx.update_ui_state
    if not update_ui_state:
        safe_print(ctx, "❌ Background sync requires blessed UI mode", style="bold red")
        return ctx, True

    # Progress callback for thread
    def on_progress(event_type: str, data: dict):
        if event_type == "init":
            update_ui_state({
                "sync_active": True,
                "sync_type": "playlist_sync",
                "sync_provider": data["provider"],
                "sync_mode": data["mode"],
                "sync_total": data["total"],
                "sync_progress": 0,
                "sync_current_name": "",
                "sync_current_status": "Initializing...",
                "sync_task_id": task_id,
                "sync_stats": {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
            })

        elif event_type == "playlist_start":
            update_ui_state({
                "sync_progress": data["index"],
                "sync_current_name": data["name"],
                "sync_current_status": f"Processing ({data['tracks']} tracks)"
            })

        elif event_type == "status_update":
            update_ui_state({"sync_current_status": data["status"]})

        elif event_type == "playlist_complete":
            # Update stats
            update_ui_state({"sync_stats": data["stats"]})

        elif event_type == "complete":
            update_ui_state({
                "sync_active": False,
                "sync_current_status": "Complete",
                "history_messages": [
                    ("", "white"),
                    (f"✓ Playlist sync complete! (task {task_id})", "green"),
                    (f"  Created: {data['created']}, Updated: {data['updated']}, Skipped: {data['skipped']}, Failed: {data['failed']}", "green"),
                    (f"  Total tracks: {data.get('total_tracks', 0)}", "green"),
                    ("", "white")
                ]
            })

    # Background thread
    def run_sync():
        try:
            sync_playlists(ctx, provider_name, full=full, progress_callback=on_progress, silent=True)
        except Exception as e:
            update_ui_state({
                "sync_active": False,
                "sync_current_status": f"Error: {e}"
            })
            safe_print(ctx, f"❌ Background sync {task_id} failed: {e}", style="bold red")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(
        target=run_sync,
        daemon=True,
        name=f"playlist-sync-{provider_name}-{task_id}"
    )
    thread.start()

    return ctx, True  # Return immediately!


def authenticate_provider(ctx: AppContext, provider_name: str) -> Tuple[AppContext, bool]:
    """Authenticate with a provider.

    Args:
        ctx: Application context
        provider_name: Provider to authenticate

    Returns:
        (ctx, True)
    """
    # Validate provider
    if not providers.provider_exists(provider_name):
        safe_print(ctx, f"❌ Unknown provider: {provider_name}", style="bold red")
        return ctx, True

    # Local provider doesn't need auth
    if provider_name == 'local':
        safe_print(ctx, "✓ Local provider doesn't require authentication", style="green")
        return ctx, True

    safe_print(ctx, f"🔐 Authenticating with {provider_name}...", style="bold yellow")

    try:
        # Debug: Check what's in the config
        safe_print(ctx, f"DEBUG: SoundCloud enabled = {ctx.config.soundcloud.enabled}")
        safe_print(ctx, f"DEBUG: Client ID = {ctx.config.soundcloud.client_id[:20] if ctx.config.soundcloud.client_id else '(empty)'}...")
        safe_print(ctx, f"DEBUG: Client Secret = {ctx.config.soundcloud.client_secret[:20] if ctx.config.soundcloud.client_secret else '(empty)'}...")

        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Inject provider config into state cache for OAuth flow
        if provider_name == 'soundcloud':
            config_dict = {
                'client_id': ctx.config.soundcloud.client_id,
                'client_secret': ctx.config.soundcloud.client_secret,
                'redirect_uri': ctx.config.soundcloud.redirect_uri
            }
            state = state.with_cache(config=config_dict)

        # Authenticate
        new_state, success = provider.authenticate(state)

        if success:
            safe_print(ctx, f"✓ Successfully authenticated with {provider_name}!", style="bold green")

            # Save auth state to database
            auth_data = new_state.cache.get('token_data', {})
            config_data = new_state.cache.get('config', {})
            database.save_provider_state(provider_name, auth_data, config_data)

        else:
            safe_print(ctx, f"❌ Authentication failed", style="bold red")

    except Exception as e:
        safe_print(ctx, f"❌ Authentication error: {e}", style="bold red")

    return ctx, True
