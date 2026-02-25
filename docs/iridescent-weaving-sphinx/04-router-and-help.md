---
task: 04-router-and-help
status: pending
depends: [03-command-handlers]
files:
  - path: src/music_minion/router.py
    action: modify
---

# Router Updates and Help Text

## Context
Update the command router to handle the new sync subcommands (pull, push) with `--dry-run` flag. Remove `sync full` and `sync status` entirely. Fix help text which previously documented non-existent commands.

## Files to Modify/Create
- src/music_minion/router.py (modify)

## Implementation Details

### Update Sync Command Routing (lines ~519-532)

Replace existing sync routing:

```python
elif command == "sync":
    if not args:
        # sync - full smart sync (find new + bidirectional)
        return sync.handle_sync_command(ctx, [])
    elif args[0] == "pull":
        # sync pull [--all] [--dry-run]
        return sync.handle_sync_pull_command(ctx, args[1:])
    elif args[0] == "push":
        # sync push [--all] [--dry-run]
        return sync.handle_sync_push_command(ctx, args[1:])
    elif args[0].startswith("--"):
        # sync --dry-run, sync --ours, sync --theirs
        return sync.handle_sync_command(ctx, args)
    else:
        logger.warning(f"Unknown sync subcommand: '{args[0]}'")
        log(
            f"Unknown sync subcommand: '{args[0]}'. "
            "Available: sync, sync pull, sync push",
            level="error",
        )
        return ctx, True
```

### Update Help Text (lines ~248-254)

Replace the Sync Commands section:

```python
Sync Commands (Local Library):
  sync              Full sync: find new files + bidirectional merge
  sync --dry-run    Preview what would change (no modifications)
  sync --ours       Resolve conflicts: database wins
  sync --theirs     Resolve conflicts: file wins
  sync pull         Import changed files → database
  sync pull --all   Full filesystem scan + import all
  sync push         Export changed metadata → files
  sync push --all   Export all metadata → files
  (all commands support --dry-run)

Sync Commands (Provider Libraries):
  sync              Sync likes/playlists from API (SoundCloud, Spotify, YouTube)
```

## Verification
1. Run `sync` - should find new files + trigger bidirectional sync (local) or provider sync (when provider active)
2. Run `sync --dry-run` - should preview changes with field-level diff for conflicts
3. Run `sync pull` - should import from changed files
4. Run `sync pull --all` - should do full filesystem scan + import all
5. Run `sync pull --dry-run` - should preview imports
6. Run `sync push` - should export changed metadata to files
7. Run `sync push --all` - should export all metadata to files
8. Run `sync push --dry-run` - should preview exports
9. Run `sync --ours` - should resolve conflicts with DB winning
10. Run `sync --theirs` - should resolve conflicts with file winning
11. Run `sync invalid` - should show error with available commands
12. Run `help` - should show updated sync documentation
