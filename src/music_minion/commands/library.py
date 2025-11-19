"""
Library management command handlers for Music Minion CLI.

Handles: library, library list, library active, library sync, library auth
"""

from typing import List, Tuple, Optional
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
            return sync_playlists(ctx, args[2])
        else:
            # library sync <provider> [--full]
            provider = None
            full = False
            for arg in args[1:]:
                if arg == "--full":
                    full = True
                else:
                    provider = arg
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


def sync_library(ctx: AppContext, provider_name: Optional[str] = None, full: bool = False) -> Tuple[AppContext, bool]:
    """Sync library from provider.

    Args:
        ctx: Application context
        provider_name: Provider to sync (None = active provider)
        full: If True, do full sync; if False, do incremental sync (default)

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

        # Sync library (incremental by default, full if --full flag provided)
        incremental = not full
        new_state, provider_tracks = provider.sync_library(state, incremental=incremental)

        if not provider_tracks:
            safe_print(ctx, f"⚠ No tracks found in {provider_name} library", style="yellow")
            return ctx, True

        # Import to database (no deduplication - creates records with source=provider)
        safe_print(ctx, f"📥 Importing {len(provider_tracks)} {provider_name} tracks to database...")

        from music_minion.domain.library.import_tracks import batch_insert_provider_tracks

        stats = batch_insert_provider_tracks(provider_tracks, provider_name)

        safe_print(ctx, f"✓ Import complete!", style="bold green")
        safe_print(ctx, f"  Created:  {stats['created']} (new {provider_name} tracks)")
        safe_print(ctx, f"  Skipped:  {stats['skipped']} (already synced)")
        safe_print(ctx, "")
        safe_print(ctx, f"💡 Tip: Run 'library match {provider_name}' to link {provider_name} tracks to local files", style="dim")

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


def sync_playlists(ctx: AppContext, provider_name: str) -> Tuple[AppContext, bool]:
    """Sync playlists from provider.

    Args:
        ctx: Application context
        provider_name: Provider to sync playlists from

    Returns:
        (updated_context, True)
    """
    # Validate provider
    if not providers.provider_exists(provider_name):
        safe_print(ctx, f"❌ Unknown provider: {provider_name}", style="bold red")
        return ctx, True

    # Can't sync from 'all' or 'local'
    if provider_name in ('all', 'local'):
        safe_print(ctx, f"❌ Cannot sync playlists from '{provider_name}'", style="bold red")
        return ctx, True

    safe_print(ctx, f"🔄 Syncing playlists from {provider_name}...", style="bold yellow")

    try:
        # Get provider module
        provider = providers.get_provider(provider_name)

        # Initialize provider state
        config = ProviderConfig(name=provider_name, enabled=True)
        state = provider.init_provider(config)

        # Check authentication
        if not state.authenticated:
            safe_print(ctx, f"❌ Not authenticated with {provider_name}", style="bold red")
            safe_print(ctx, f"Run: library auth {provider_name}")
            return ctx, True

        # Get playlists from provider
        state, playlists = provider.get_playlists(state)

        if not playlists:
            safe_print(ctx, f"⚠ No playlists found in {provider_name}", style="yellow")
            return ctx, True

        safe_print(ctx, f"Found {len(playlists)} playlists", style="green")
        safe_print(ctx, "")

        # Import each playlist
        from music_minion.domain import playlists as playlist_crud

        created_count = 0
        skipped_count = 0
        total_tracks_added = 0

        for i, pl_data in enumerate(playlists, 1):
            pl_name = pl_data['name']
            pl_id = pl_data['id']
            pl_track_count = pl_data.get('track_count', 0)

            safe_print(ctx, f"[{i}/{len(playlists)}] {pl_name} ({pl_track_count} tracks)")

            # Check if playlist already exists
            provider_id_field = f"{provider_name}_playlist_id"
            existing = None
            with database.get_db_connection() as conn:
                cursor = conn.execute(
                    f"SELECT id, name FROM playlists WHERE {provider_id_field} = ?",
                    (pl_id,)
                )
                existing = cursor.fetchone()

            if existing:
                safe_print(ctx, f"  ⏭ Skipped (already imported)", style="dim")
                skipped_count += 1
                continue

            # Get playlist tracks from provider
            state, provider_tracks = provider.get_playlist_tracks(state, pl_id)

            if not provider_tracks:
                safe_print(ctx, f"  ⚠ No tracks found", style="yellow")
                continue

            # Look up tracks in database by provider ID
            safe_print(ctx, f"  🔍 Looking up {len(provider_tracks)} tracks in database...")

            track_ids = []
            provider_id_col = f"{provider_name}_id"

            with database.get_db_connection() as conn:
                for track_id, metadata in provider_tracks:
                    cursor = conn.execute(
                        f"SELECT id FROM tracks WHERE {provider_id_col} = ?",
                        (track_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        track_ids.append(row['id'])

            found_pct = (len(track_ids) / len(provider_tracks) * 100) if provider_tracks else 0
            safe_print(ctx, f"  ✓ Found {len(track_ids)}/{len(provider_tracks)} tracks in database ({found_pct:.0f}%)", style="green")

            if len(track_ids) < len(provider_tracks):
                missing = len(provider_tracks) - len(track_ids)
                safe_print(ctx, f"  ⚠ {missing} tracks not found (run 'library sync {provider_name}' first)", style="yellow")

            # Create playlist in database
            playlist_id = playlist_crud.create_playlist(
                name=pl_name,
                playlist_type='manual',
                description=pl_data.get('description')
            )

            # Set provider playlist ID
            with database.get_db_connection() as conn:
                conn.execute(
                    f"UPDATE playlists SET {provider_id_field} = ? WHERE id = ?",
                    (pl_id, playlist_id)
                )
                conn.commit()

            # Add tracks to playlist
            if track_ids:
                for track_id in track_ids:
                    playlist_crud.add_track_to_playlist(playlist_id, track_id)

                total_tracks_added += len(track_ids)

            safe_print(ctx, f"  ✅ Created '{pl_name}' with {len(track_ids)} tracks", style="bold green")
            created_count += 1

        # Summary
        safe_print(ctx, "")
        safe_print(ctx, "=" * 50)
        safe_print(ctx, f"✓ Playlist sync complete!", style="bold green")
        safe_print(ctx, f"  Created:  {created_count} playlists")
        safe_print(ctx, f"  Skipped:  {skipped_count} (already imported)")
        safe_print(ctx, f"  Tracks:   {total_tracks_added} total tracks added")
        safe_print(ctx, "")

        if created_count > 0:
            safe_print(ctx, f"💡 Tip: Switch to {provider_name} library to view these playlists", style="dim")
            safe_print(ctx, f"    library active {provider_name}", style="dim")
            safe_print(ctx, "")
            safe_print(ctx, f"💡 To link {provider_name} tracks to local files, run:", style="dim")
            safe_print(ctx, f"    library match {provider_name}", style="dim")

    except Exception as e:
        safe_print(ctx, f"❌ Playlist sync failed: {e}", style="bold red")
        import traceback
        traceback.print_exc()

    return ctx, True


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
