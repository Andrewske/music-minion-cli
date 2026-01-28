"""
Library management command handlers for Music Minion CLI.

Handles: library, library list, library active, library sync, library auth, library device
"""

import argparse
import re
import threading
from typing import Any, Callable, Optional

from music_minion.context import AppContext
from music_minion.core import config, database
from music_minion.core.output import log
from music_minion.domain.library import providers
from music_minion.domain.library.provider import ProviderConfig, ProviderState

# Removed: old sync_provider_tracks import (replaced with batch_insert_provider_tracks)

# Global sync state (thread-safe)
_sync_state_lock = threading.Lock()
_sync_state: Optional[dict[str, Any]] = None


def _save_provider_state_to_db(provider_name: str, state: ProviderState) -> None:
    """Save provider state to database after sync completes."""

    # Extract cache data and auth data from state
    cache_data = state.cache if state.cache else {}

    # Extract token_data from cache for auth_data column (needed for token refresh)
    auth_data = cache_data.get("token_data", {})

    # Save config with remaining cache data for next sync
    config_data = {"cache": cache_data}

    database.save_provider_state(provider_name, auth_data, config_data)


def get_sync_state() -> Optional[dict[str, Any]]:
    """Get current sync state (thread-safe)."""
    with _sync_state_lock:
        return _sync_state.copy() if _sync_state else None


def _update_sync_state(updates: dict[str, Any]) -> None:
    """Update sync state (thread-safe, internal use only)."""
    global _sync_state
    with _sync_state_lock:
        if _sync_state is None:
            _sync_state = {}
        _sync_state.update(updates)


def _clear_sync_state() -> None:
    """Clear sync state (thread-safe, internal use only)."""
    global _sync_state
    with _sync_state_lock:
        _sync_state = None


def _threaded_sync_worker(ctx: AppContext, provider_name: str, full: bool) -> None:
    """Background worker thread for library syncing.

    Note: As of blessed-aware log() implementation:
    - Blessed mode: log() routes ALL messages through UI callback (visible in command history)
    - CLI mode: silent_logging=True suppresses stdout printing (backwards compatibility)
    """
    import threading

    # Set silent_logging for CLI mode (suppresses stdout printing)
    # In blessed mode, this flag is ignored - messages route through UI callback
    threading.current_thread().silent_logging = True

    try:
        # Initialize state
        _update_sync_state(
            {
                "phase": "init",
                "provider": provider_name,
                "mode": "full" if full else "incremental",
                "tracks_fetched": 0,
                "tracks_imported": 0,
                "error": None,
                "completed": False,
                "stats": {"created": 0, "skipped": 0},
            }
        )

        # Progress callback to update UI
        def progress_callback(event_type: str, data: dict) -> None:
            if event_type == "tracks_fetched":
                _update_sync_state(
                    {
                        "phase": "fetching",
                        "tracks_fetched": data.get("total", 0),
                        "status": data.get("status", ""),
                    }
                )
            elif event_type == "importing":
                _update_sync_state(
                    {"phase": "importing", "status": data.get("status", "")}
                )
            elif event_type == "complete":
                _update_sync_state(
                    {
                        "completed": True,
                        "stats": {
                            "created": data.get("created", 0),
                            "skipped": data.get("skipped", 0),
                        },
                    }
                )
            elif event_type == "error":
                _update_sync_state({"completed": True, "error": data.get("error")})

        # Run sync with progress callback
        sync_library(ctx, provider_name, full=full, progress_callback=progress_callback)

    except Exception as e:
        _update_sync_state({"completed": True, "error": str(e)})
    finally:
        # Always clear the flag
        threading.current_thread().silent_logging = False


def sync_library_background(
    ctx: AppContext, provider_name: str, full: bool = False
) -> tuple[AppContext, bool]:
    """Start library sync in background thread.

    Args:
        ctx: Application context
        provider_name: Provider to sync
        full: If True, do full sync; if False, do incremental sync

    Returns:
        (ctx, True) - Returns immediately while sync runs in background
    """
    # Clear any previous sync state
    _clear_sync_state()

    # Start worker thread
    thread = threading.Thread(
        target=_threaded_sync_worker, args=(ctx, provider_name, full), daemon=True
    )
    thread.start()

    return ctx, True


def _threaded_playlist_sync_worker(
    ctx: AppContext, provider_name: str, full: bool
) -> None:
    """Background worker thread for playlist syncing."""
    import threading

    # Suppress stdout printing from log() calls (prevents UI interference)
    threading.current_thread().silent_logging = True

    try:
        # Initialize state
        _update_sync_state(
            {
                "phase": "playlists",
                "provider": provider_name,
                "mode": "full" if full else "incremental",
                "playlists_processed": 0,
                "total_playlists": 0,
                "error": None,
                "completed": False,
                "stats": {"created": 0, "updated": 0, "skipped": 0, "failed": 0},
            }
        )

        # Progress callback to update UI
        def progress_callback(event_type: str, data: dict) -> None:
            if event_type == "init":
                _update_sync_state(
                    {
                        "total_playlists": data.get("total", 0),
                        "phase": "syncing_playlists",
                    }
                )
            elif event_type == "playlist_start":
                _update_sync_state(
                    {
                        "playlists_processed": data.get("index", 0),
                        "current_playlist": data.get("name", ""),
                    }
                )
            elif event_type == "playlist_complete":
                stats = data.get("stats", {})
                _update_sync_state({"stats": stats})
            elif event_type == "complete":
                stats = (
                    data.get("stats", {})
                    if "stats" in data
                    else {
                        "created": data.get("created", 0),
                        "updated": data.get("updated", 0),
                        "skipped": data.get("skipped", 0),
                        "failed": data.get("failed", 0),
                    }
                )
                _update_sync_state({"completed": True, "stats": stats})
            elif event_type == "error":
                _update_sync_state({"completed": True, "error": data.get("error")})

        # Run playlist sync with progress callback
        sync_playlists(
            ctx,
            provider_name,
            full=full,
            progress_callback=progress_callback,
            silent=True,
        )

    except Exception as e:
        _update_sync_state({"completed": True, "error": str(e)})
    finally:
        # Always clear the flag
        threading.current_thread().silent_logging = False


def sync_playlists_background(
    ctx: AppContext, provider_name: str, full: bool = False
) -> tuple[AppContext, bool]:
    """Start playlist sync in background thread.

    Args:
        ctx: Application context
        provider_name: Provider to sync playlists from
        full: If True, force full re-sync of all playlists

    Returns:
        (ctx, True) - Returns immediately while sync runs in background
    """
    # Clear any previous sync state
    _clear_sync_state()

    # Start worker thread
    thread = threading.Thread(
        target=_threaded_playlist_sync_worker,
        args=(ctx, provider_name, full),
        daemon=True,
    )
    thread.start()

    return ctx, True


def handle_library_command(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
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
            log(
                "  library sync soundcloud likes        # Sync tracks only",
                level="info",
            )
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

    elif args[0] == "device":
        return handle_device_commands(ctx, args[1:])

    else:
        log(f"❌ Unknown library command: {args[0]}", level="error")
        log("Available: list, active, sync, auth, device", level="info")
        return ctx, True


def handle_library_list(ctx: AppContext) -> tuple[AppContext, bool]:
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


def show_active_library(ctx: AppContext) -> tuple[AppContext, bool]:
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


def switch_active_library(ctx: AppContext, provider: str) -> tuple[AppContext, bool]:
    """Switch to a different library provider.

    Args:
        ctx: Application context
        provider: Provider name ('local', 'soundcloud', 'spotify', 'youtube')
             Note: 'all' is supported internally but hidden from users

    Returns:
        (updated_context, True)
    """
    # Valid providers (excluding 'all' which is internal-only)
    valid_providers = ["local", "soundcloud", "spotify", "youtube"]

    # Allow 'all' for internal use only
    if provider not in valid_providers and provider != "all":
        log(f"❌ Invalid provider: {provider}", level="error")
        log(f"Available: {', '.join(valid_providers)}", level="info")
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

    # Restore active playlist for this library (if it has one)
    # The active_playlist table now tracks per-library active playlists
    # No action needed - get_active_playlist() will automatically use the new library
    # This allows seamless switching between libraries with their own active playlists

    # Auto-sync streaming providers (incremental sync is fast)
    if provider == "spotify" and ctx.config.spotify.enabled:
        log("🔄 Auto-syncing Spotify library (incremental)...", level="info")
        if ctx.ui_mode == "blessed" and ctx.update_ui_state:
            ctx, _ = sync_library_background(ctx, provider, full=False)
        else:
            ctx, _ = sync_library(ctx, provider, full=False)
            log("✓ Spotify sync complete", level="info")
    elif provider == "soundcloud" and ctx.config.soundcloud.enabled:
        log("🔄 Auto-syncing SoundCloud library (incremental)...", level="info")
        if ctx.ui_mode == "blessed" and ctx.update_ui_state:
            ctx, _ = sync_library_background(ctx, provider, full=False)
        else:
            ctx, _ = sync_library(ctx, provider, full=False)
            log("✓ SoundCloud sync complete", level="info")

    # Reload tracks based on provider
    filtered = database.filter_tracks_by_library(database.get_all_tracks(), provider)

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
) -> tuple[AppContext, bool]:
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

    # At this point provider_name is guaranteed to be a string
    provider_name = str(provider_name)

    # Validate provider
    if not providers.provider_exists(provider_name):
        log(f"❌ Unknown provider: {provider_name}", level="error")
        return ctx, True

    # Can't sync 'all' - it's a filter, not a provider
    if provider_name == "all":
        log("❌ Cannot sync 'all' - specify a provider", level="error")
        return ctx, True

    log(f"🔄 Syncing from {provider_name}...", level="info")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Load provider state from database (includes cached sync data for incremental sync)
        assert provider_name is not None, (
            "provider_name should not be None at this point"
        )
        db_state = database.load_provider_state(provider_name)
        if db_state:
            # Reconstruct state from database with existing cache
            config = ProviderConfig(name=provider_name, enabled=True)
            state = provider.init_provider(config)
        else:
            # Initialize fresh state if no database record exists
            config = ProviderConfig(name=provider_name, enabled=True)
            state = provider.init_provider(config)

        # Inject provider credentials into state cache (required for OAuth refresh)
        if provider_name == "soundcloud":
            config_dict = {
                "client_id": ctx.config.soundcloud.client_id,
                "client_secret": ctx.config.soundcloud.client_secret,
                "redirect_uri": ctx.config.soundcloud.redirect_uri,
            }
            state = state.with_cache(config=config_dict)
        elif provider_name == "spotify":
            config_dict = {
                "client_id": ctx.config.spotify.client_id,
                "client_secret": ctx.config.spotify.client_secret,
                "redirect_uri": ctx.config.spotify.redirect_uri,
            }
            state = state.with_cache(config=config_dict)

        # Restore cached values for incremental sync optimization (after credentials)
        # IMPORTANT: Never restore token_data from database - file system is source of truth
        if db_state and db_state.get("config"):
            cache_data = db_state["config"].get("cache", {})
            # Remove token_data if present - init_provider() loads fresh token from file
            cache_data.pop("token_data", None)
            state = state.with_cache(**cache_data)

        # Check authentication
        if not state.authenticated and provider_name != "local":
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
            # Check if this is due to authentication failure vs genuinely no tracks
            if not new_state.authenticated:
                log(
                    f"❌ Authentication failed for {provider_name}. Please re-authenticate with: library auth {provider_name}",
                    level="error",
                )
            else:
                message = f"⚠ No tracks found in {provider_name} library"
                if incremental:
                    message += " (incremental mode - all tracks already synced)"
                    log(message, level="warning")
                    log("💡 Tip: Use '--full' flag to re-sync all tracks", level="info")
                else:
                    log(message, level="warning")

            # Save updated provider state even when no tracks found (updates cache/timestamps)
            # This is important for incremental sync - the cache/timestamps get updated even when no new tracks
            _save_provider_state_to_db(provider_name, new_state)

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

        if progress_callback:
            progress_callback(
                "importing", {"status": f"Importing {len(provider_tracks)} tracks..."}
            )

        from music_minion.domain.library.import_tracks import (
            batch_insert_provider_tracks,
        )

        stats = batch_insert_provider_tracks(provider_tracks, provider_name)

        log("✓ Import complete!", level="info")
        log(
            f"  Created:  {stats['created']} (new {provider_name} tracks)", level="info"
        )
        log(f"  Skipped:  {stats['skipped']} (already synced)", level="info")
        log("", level="info")
        log(
            f"💡 Tip: Run 'library match {provider_name}' to link {provider_name} tracks to local files",
            level="info",
        )

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

            new_state2, playlists = provider.get_playlists(new_state, full=full)

            if playlists:
                log(f"Found {len(playlists)} playlists:", level="info")
                for i, pl in enumerate(playlists[:5], 1):
                    log(
                        f"  {i}. {pl['name']} ({pl['track_count']} tracks)",
                        level="info",
                    )

                if len(playlists) > 5:
                    log(f"  ... and {len(playlists) - 5} more", level="info")

                log("", level="info")
                log(
                    "💡 Tip: Use 'playlist import soundcloud' to import playlists",
                    level="info",
                )

        # Save updated provider state to database for next incremental sync
        if new_state and new_state != state:
            _save_provider_state_to_db(provider_name, new_state)

        # Reload tracks if this is the active provider
        active_provider = database.get_active_provider()

        if active_provider == provider_name or active_provider == "all":
            # Reload tracks for synced provider
            ctx, _ = switch_active_library(ctx, provider_name)

    except Exception as e:
        log(f"❌ Sync failed: {e}", level="error")
        if progress_callback:
            progress_callback("error", {"error": str(e)})
        import traceback

        traceback.print_exc()

    return ctx, True


def sync_playlists(
    ctx: AppContext,
    provider_name: str,
    full: bool = False,
    progress_callback: Optional[Callable[[str, dict], None]] = None,
    silent: bool = False,
) -> tuple[AppContext, bool]:
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
        if silent:
            return
        log(message, level="info")

    # Validate provider
    if not providers.provider_exists(provider_name):
        print_if_not_silent(f"❌ Unknown provider: {provider_name}")
        return ctx, True

    # Can't sync from 'all' or 'local'
    if provider_name in ("all", "local"):
        print_if_not_silent(f"❌ Cannot sync playlists from '{provider_name}'")
        return ctx, True

    sync_mode = "full" if full else "incremental"
    log(f"🔄 Syncing playlists from {provider_name} ({sync_mode})...", level="info")
    print_if_not_silent(
        f"🔄 Syncing playlists from {provider_name} ({sync_mode})...",
    )

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state - load from database if available (includes cached sync data for incremental sync)
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Load cached state from database for incremental sync optimization
        db_state = database.load_provider_state(provider_name)
        if db_state and db_state.get("config"):
            cache_data = db_state["config"].get("cache", {})
            if cache_data:
                state = state.with_cache(**cache_data)

        # Check authentication
        if not state.authenticated:
            log(f"❌ Not authenticated with {provider_name}", level="error")
            print_if_not_silent(f"❌ Not authenticated with {provider_name}")
            print_if_not_silent(f"Run: library auth {provider_name}")
            return ctx, True

        # Get playlists from provider
        import time

        print_if_not_silent(f"📋 Fetching playlists from {provider_name}...")
        fetch_start = time.time()
        state, playlists = provider.get_playlists(state, full=full)
        fetch_time = time.time() - fetch_start
        log(
            f"Fetched {len(playlists) if playlists else 0} playlists metadata in {fetch_time:.2f}s",
            level="debug",
        )

        if not playlists:
            # Check if this is due to authentication failure vs genuinely no playlists
            if not state.authenticated:
                log(
                    f"❌ Authentication failed for {provider_name}. Please re-authenticate with: library auth {provider_name}",
                    level="error",
                )
                print_if_not_silent(
                    f"❌ Authentication failed for {provider_name}. Please re-authenticate with: library auth {provider_name}"
                )
            else:
                log(f"⚠ No playlists found in {provider_name}", level="warning")
                print_if_not_silent(f"⚠ No playlists found in {provider_name}")
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

        print_if_not_silent(f"✓ Found {len(existing_playlists_map)} existing playlists")

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

            # Apply incremental sync filter BEFORE fetching tracks
            existing = existing_playlists_map.get(pl_id)
            if existing and not full and pl_last_modified:
                existing_modified = existing["provider_last_modified"]
                if existing_modified and pl_last_modified <= existing_modified:
                    # Skip - no changes since last sync
                    skipped_count += 1
                    continue

            # Fetch tracks for this playlist (metadata-only API means we need individual fetches)
            state, provider_tracks, _ = provider.get_playlist_tracks(state, pl_id)

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
        log(
            f"Playlist filter: {skipped_count} skipped (unchanged), {len(playlists_to_sync)} syncing",
            level="info",
        )

        if not playlists_to_sync:
            print_if_not_silent(
                f"\n⚠ No playlists need syncing ({skipped_count} unchanged)"
            )
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
            print_if_not_silent(f"📥 Auto-importing {missing_count} missing tracks...")

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
                            print_if_not_silent("  💾 Updating existing playlist...")
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
                            # Also update spotify_snapshot_id if provider is Spotify
                            if provider_name == "spotify":
                                conn.execute(
                                    """
                                    UPDATE playlists
                                    SET last_synced_at = ?,
                                        provider_last_modified = ?,
                                        provider_created_at = COALESCE(?, provider_created_at),
                                        track_count = ?,
                                        spotify_snapshot_id = ?,
                                        library = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """,
                                    (
                                        time.time(),
                                        pl_last_modified,
                                        pl_created_at,
                                        len(track_ids),
                                        pl_last_modified,  # snapshot_id
                                        provider_name,
                                        playlist_id,
                                    ),
                                )
                            else:
                                conn.execute(
                                    """
                                    UPDATE playlists
                                    SET last_synced_at = ?,
                                        provider_last_modified = ?,
                                        provider_created_at = COALESCE(?, provider_created_at),
                                        track_count = ?,
                                        library = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """,
                                    (
                                        time.time(),
                                        pl_last_modified,
                                        pl_created_at,
                                        len(track_ids),
                                        provider_name,
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

                            print_if_not_silent("  💾 Creating playlist...")
                            update_progress(
                                "status_update", {"status": "Creating playlist..."}
                            )

                            # Create playlist in database (inline to use same transaction)
                            cursor = conn.execute(
                                """
                                INSERT INTO playlists (name, type, description, track_count, library, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """,
                                (
                                    final_name,
                                    "manual",
                                    pl_data.get("description"),
                                    len(track_ids),
                                    provider_name,
                                ),
                            )
                            playlist_id = cursor.lastrowid

                            # Set provider playlist ID and timestamps
                            # Also set spotify_snapshot_id if provider is Spotify
                            if provider_name == "spotify":
                                conn.execute(
                                    f"""
                                    UPDATE playlists
                                    SET {provider_id_field} = ?,
                                        last_synced_at = ?,
                                        provider_last_modified = ?,
                                        provider_created_at = ?,
                                        spotify_snapshot_id = ?
                                    WHERE id = ?
                                """,
                                    (
                                        pl_id,
                                        datetime.now().isoformat(),
                                        pl_last_modified,
                                        pl_created_at,
                                        pl_last_modified,  # snapshot_id
                                        playlist_id,
                                    ),
                                )
                            else:
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
                print_if_not_silent("\n✓ Committed all playlist changes to database")

            except Exception as e:
                conn.rollback()
                log(f"❌ Transaction failed, rolled back: {e}", level="error")
                print_if_not_silent(f"❌ Transaction failed, rolled back: {e}")
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


def handle_auth_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Authenticate with the currently active library provider.

    Args:
        ctx: Application context

    Returns:
        (ctx, True)
    """
    # Get active provider from database
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_provider = row["provider"] if row else "local"

    # Validate provider
    if active_provider == "local":
        log("✓ Local provider doesn't require authentication", level="info")
        return ctx, True

    if active_provider == "all":
        log(
            "❌ Cannot authenticate 'all' - switch to a specific provider first",
            level="error",
        )
        log("Available: soundcloud, spotify, youtube", level="info")
        return ctx, True

    # Authenticate the active provider
    return authenticate_provider(ctx, active_provider)


def authenticate_provider(
    ctx: AppContext, provider_name: str
) -> tuple[AppContext, bool]:
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
        elif provider_name == "spotify":
            config_dict = {
                "client_id": ctx.config.spotify.client_id,
                "client_secret": ctx.config.spotify.client_secret,
                "redirect_uri": ctx.config.spotify.redirect_uri,
            }
            state = state.with_cache(config=config_dict)

        # Authenticate
        new_state, success = provider.authenticate(state)

        if success:
            log(f"✓ Successfully authenticated with {provider_name}!", level="info")

            # Save auth state to database
            auth_data = new_state.cache.get("token_data", {})
            config_data = new_state.cache.get("config", {})
            database.save_provider_state(provider_name, auth_data, config_data)

        else:
            log("❌ Authentication failed", level="error")

    except Exception as e:
        log(f"❌ Authentication error: {e}", level="error")

    return ctx, True


def handle_device_commands(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
    """Handle device management commands for Spotify.

    Args:
        ctx: Application context
        args: Command arguments (list, set, clear)

    Returns:
        (updated_context, should_continue)
    """
    if not args or args[0] == "list":
        return list_spotify_devices(ctx)
    elif args[0] == "set":
        if len(args) < 2:
            log("❌ Usage: library device set <device_name_or_id>", level="error")
            return ctx, True
        return set_spotify_device(ctx, args[1])
    elif args[0] == "clear":
        return clear_spotify_device(ctx)
    else:
        log(f"❌ Unknown device command: {args[0]}", level="error")
        log("Available: list, set, clear", level="info")
        return ctx, True


def list_spotify_devices(ctx: AppContext) -> tuple[AppContext, bool]:
    """List available Spotify devices using command palette.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.domain.library.providers import spotify
    import shlex

    # Check if Spotify is enabled
    if not ctx.config.spotify.enabled:
        log("❌ Spotify is not enabled in configuration", level="error")
        return ctx, True

    # Get Spotify provider state
    spotify_state = ctx.provider_states.get("spotify")
    if not spotify_state or not spotify_state.authenticated:
        log(
            "❌ Spotify is not authenticated. Run 'library auth spotify' first.",
            level="error",
        )
        return ctx, True

    try:
        # Get available devices
        devices = spotify.api._spotify_get_devices(spotify_state)

        if not devices:
            log(
                "⚠ No Spotify devices found. Open Spotify on a device first.",
                level="warning",
            )
            return ctx, True

        # Build device items for command palette
        device_items = []
        preferred_id = ctx.config.spotify.preferred_device_id
        preferred_name = ctx.config.spotify.preferred_device_name

        for device in devices:
            name = device.get("name", "Unknown")
            device_id = device.get("id", "unknown")
            device_type = device.get("type", "unknown")
            is_active = device.get("is_active", False)
            volume = device.get("volume_percent", 0)

            # Build display name with status indicators
            status_indicators = []
            if is_active:
                status_indicators.append("🟢")
            if device_id == preferred_id or name == preferred_name:
                status_indicators.append("⭐")

            display_name = f"{' '.join(status_indicators)} {name} ({device_type})"

            # Build description with details
            description_parts = [f"ID: {device_id}", f"Volume: {volume}%"]
            if is_active:
                description_parts.append("Currently active")

            description = " | ".join(description_parts)

            # Command to execute when selected
            command = f"library device set {shlex.quote(name)}"

            device_items.append((display_name, description, command, device_id))

        # Signal UI to show device palette
        ctx = ctx.with_ui_action(
            {
                "type": "show_device_palette",
                "device_items": device_items,
                "device_count": len(devices),
            }
        )

    except Exception as e:
        log(f"❌ Error listing devices: {e}", level="error")

    return ctx, True


def set_spotify_device(
    ctx: AppContext, device_identifier: str
) -> tuple[AppContext, bool]:
    """Set preferred Spotify device.

    Args:
        ctx: Application context
        device_identifier: Device name or ID to set as preferred

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.domain.library.providers import spotify

    # Check if Spotify is enabled
    if not ctx.config.spotify.enabled:
        log("❌ Spotify is not enabled in configuration", level="error")
        return ctx, True

    # Get Spotify provider state
    spotify_state = ctx.provider_states.get("spotify")
    if not spotify_state or not spotify_state.authenticated:
        log(
            "❌ Spotify is not authenticated. Run 'library auth spotify' first.",
            level="error",
        )
        return ctx, True

    try:
        # Get available devices
        devices = spotify.api._spotify_get_devices(spotify_state)

        if not devices:
            log(
                "⚠ No Spotify devices found. Open Spotify on a device first.",
                level="warning",
            )
            return ctx, True

        # Find matching device
        matching_device = None
        for device in devices:
            name = device.get("name", "")
            device_id = device.get("id", "")

            if device_identifier == name or device_identifier == device_id:
                matching_device = device
                break

        if not matching_device:
            log(
                f"❌ Device '{device_identifier}' not found in available devices",
                level="error",
            )
            log("Run 'library device list' to see available devices", level="info")
            return ctx, True

        # Update config with preferred device
        device_name = matching_device.get("name", "")
        device_id = matching_device.get("id", "")

        ctx.config.spotify.preferred_device_name = device_name
        ctx.config.spotify.preferred_device_id = device_id

        # Save config to file
        if config.save_config(ctx.config):
            log(f"✓ Set preferred device to: {device_name}", level="info")
            log(f"  Device ID: {device_id}", level="info")
        else:
            log("❌ Failed to save device preference", level="error")

    except Exception as e:
        log(f"❌ Error setting device: {e}", level="error")

    return ctx, True


def clear_spotify_device(ctx: AppContext) -> tuple[AppContext, bool]:
    """Clear preferred Spotify device setting.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if there's a preferred device to clear
    if (
        not ctx.config.spotify.preferred_device_id
        and not ctx.config.spotify.preferred_device_name
    ):
        log("ℹ No preferred device is currently set", level="info")
        return ctx, True

    try:
        # Clear preferred device settings
        current_device = (
            ctx.config.spotify.preferred_device_name
            or ctx.config.spotify.preferred_device_id
        )
        ctx.config.spotify.preferred_device_name = ""
        ctx.config.spotify.preferred_device_id = ""

        # Save config to file
        if config.save_config(ctx.config):
            log(f"✓ Cleared preferred device: {current_device}", level="info")
            log(
                "Device selection will now use automatic priority (active → first available)",
                level="info",
            )
        else:
            log("❌ Failed to clear device preference", level="error")

    except Exception as e:
        log(f"❌ Error clearing device preference: {e}", level="error")

    return ctx, True


# YouTube import commands


def handle_youtube_add(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
    """Import a single YouTube video with optional metadata.

    Usage: youtube add <url> [--artist <name>] [--title <name>] [--album <name>]

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (ctx, True)
    """
    parser = argparse.ArgumentParser(
        prog="youtube add", description="Import a YouTube video"
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--artist", help="Artist name (default: video uploader)")
    parser.add_argument("--title", help="Track title (default: video title)")
    parser.add_argument("--album", help="Album name (default: empty)")

    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        # argparse calls sys.exit on error, catch it
        return ctx, True

    url = parsed.url
    artist = parsed.artist
    title = parsed.title
    album = parsed.album

    log(f"📥 Importing YouTube video...", level="info")
    if artist or title or album:
        log(
            f"   Using custom metadata: {artist or '[uploader]'} - {title or '[video title]'}",
            level="info",
        )

    try:
        # Import from the youtube provider
        from music_minion.domain.library.providers import youtube

        track = youtube.import_single_video(
            url=url, artist=artist, title=title, album=album
        )

        log(f"✓ Imported: {track.artist} - {track.title}", level="info")
        log(f"  File: {track.local_path}", level="info")
        log(f"  Track ID: {track.id}", level="info")

    except youtube.DuplicateVideoError as e:
        log(f"⚠ Video already imported as track #{e.track_id}", level="warning")
    except youtube.InvalidYouTubeURLError as e:
        log(f"❌ Invalid YouTube URL: {e}", level="error")
    except youtube.AgeRestrictedError as e:
        log(f"❌ {e}", level="error")
        log("   Age-restricted videos require login (not supported)", level="info")
    except youtube.VideoUnavailableError as e:
        log(f"❌ {e}", level="error")
    except youtube.InsufficientSpaceError as e:
        log(f"❌ {e}", level="error")
    except youtube.YouTubeError as e:
        log(f"❌ Import failed: {e}", level="error")
    except Exception as e:
        log(f"❌ Unexpected error: {e}", level="error")

    return ctx, True


def handle_youtube_add_playlist(
    ctx: AppContext, args: list[str]
) -> tuple[AppContext, bool]:
    """Import all videos from a YouTube playlist.

    Usage: youtube add-playlist <playlist_id or url>

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (ctx, True)
    """
    parser = argparse.ArgumentParser(
        prog="youtube add-playlist", description="Import a YouTube playlist"
    )
    parser.add_argument("playlist", help="YouTube playlist ID or URL")

    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        # argparse calls sys.exit on error, catch it
        return ctx, True

    playlist_arg = parsed.playlist

    # Extract playlist ID from URL if necessary
    # Pattern: list=([a-zA-Z0-9_-]+)
    match = re.search(r"list=([a-zA-Z0-9_-]+)", playlist_arg)
    if match:
        playlist_id = match.group(1)
        log(f"📥 Importing playlist: {playlist_id}", level="info")
    else:
        # Assume it's already a playlist ID
        playlist_id = playlist_arg
        log(f"📥 Importing playlist: {playlist_id}", level="info")

    try:
        # Import from the youtube provider
        from music_minion.domain.library.providers import youtube

        result = youtube.import_playlist(playlist_id)

        log(f"✓ Playlist import complete!", level="info")
        log(f"  Imported: {result.imported_count} tracks", level="info")
        log(f"  Skipped: {result.skipped_count} duplicates", level="info")

        if result.failed_count > 0:
            log(f"  Failed: {result.failed_count} videos", level="warning")
            for video_id, error in result.failures[:5]:  # Show first 5 failures
                log(f"    - {video_id}: {error}", level="warning")
            if len(result.failures) > 5:
                log(
                    f"    ... and {len(result.failures) - 5} more failures",
                    level="warning",
                )

    except youtube.InsufficientSpaceError as e:
        log(f"❌ {e}", level="error")
    except youtube.YouTubeError as e:
        log(f"❌ Import failed: {e}", level="error")
    except Exception as e:
        log(f"❌ Unexpected error: {e}", level="error")

    return ctx, True
