---
task: 02-sync-engine-core
status: pending
depends: [01-database-migration]
files:
  - path: src/music_minion/domain/sync/engine.py
    action: modify
---

# Core Sync Engine Functions

## Context
Implement the core bidirectional sync logic with content hashing for change detection. These pure functions determine what action (import/export/skip/conflict) is needed for each track by comparing file metadata hash against stored hash and checking DB modification timestamps.

## Files to Modify/Create
- src/music_minion/domain/sync/engine.py (modify)

## Implementation Details

### Data Types

```python
from enum import Enum
from dataclasses import dataclass

class SyncAction(Enum):
    SKIP = "skip"
    IMPORT = "import"      # File changed, DB didn't
    EXPORT = "export"      # DB changed, file didn't
    CONFLICT = "conflict"  # Both changed

class ConflictStrategy(Enum):
    OURS = "ours"       # DB wins
    THEIRS = "theirs"   # File wins

@dataclass(frozen=True)
class SyncResult:
    track_id: int
    local_path: str
    action: SyncAction
    computed_file_hash: str | None = None  # Needed to update DB after sync
    file_metadata: dict | None = None
    db_metadata: dict | None = None
    conflict_fields: list[str] | None = None
```

### Functions to Add

```python
def compute_metadata_hash(metadata: dict) -> str:
    """Compute deterministic hash of structured metadata fields.

    Args:
        metadata: Dict with keys: key_signature, bpm, title, artist, album, genre, year, comment

    Returns:
        16-character hex hash string
    """
    import hashlib

    def normalize(key: str, value: Any) -> str:
        if value is None or value == '':
            return ''
        if key == 'bpm':
            # Normalize floats: 128.0, 128.00, 128 -> "128.0"
            try:
                return str(round(float(value), 1))
            except (ValueError, TypeError):
                return ''
        return str(value)

    fields = ['key_signature', 'bpm', 'title', 'artist', 'album', 'genre', 'year', 'comment']
    values = [normalize(f, metadata.get(f)) for f in fields]
    return hashlib.sha256('|'.join(values).encode()).hexdigest()[:16]


def extract_file_structured_metadata(local_path: str) -> dict:
    """Extract structured metadata fields from audio file.

    Uses existing extract_track_metadata from domain.library.metadata.
    Returns dict with: title, artist, album, genre, year, bpm, key_signature, comment
    """
    from music_minion.domain.library.metadata import extract_track_metadata
    track = extract_track_metadata(local_path)
    return {
        'title': track.title,
        'artist': track.artist,
        'album': track.album,
        'genre': track.genre,
        'year': track.year,
        'bpm': track.bpm,
        'key_signature': track.key,
        'comment': track.comment,
    }


def determine_sync_action(
    track_id: int,
    local_path: str,
    stored_file_hash: str | None,
    metadata_updated_at: datetime | None,
    last_synced_at: datetime | None,
) -> SyncResult:
    """Determine what sync action is needed for a track.

    Logic:
    - file_changed = current file hash != stored hash (or stored hash is NULL)
    - db_changed = metadata_updated_at > last_synced_at (and both are not NULL)

    Returns SyncResult with action: IMPORT, EXPORT, CONFLICT, or SKIP
    """
    # Extract current file metadata and compute hash
    try:
        file_metadata = extract_file_structured_metadata(local_path)
        current_hash = compute_metadata_hash(file_metadata)
    except Exception:
        # File unreadable - skip
        return SyncResult(track_id=track_id, local_path=local_path, action=SyncAction.SKIP)

    # Determine if file changed
    # NULL stored_hash means never synced -> treat as file changed (import to initialize)
    file_changed = stored_file_hash is None or current_hash != stored_file_hash

    # Determine if DB changed
    # Both timestamps must exist and metadata_updated_at must be after last_synced_at
    db_changed = (
        metadata_updated_at is not None
        and last_synced_at is not None
        and metadata_updated_at > last_synced_at
    )

    # Determine action based on change matrix
    db_metadata = None
    conflict_fields = None

    if file_changed and db_changed:
        action = SyncAction.CONFLICT
        # Fetch DB values for field-level diff
        db_metadata = get_track_metadata_from_db(track_id)
        conflict_fields = [
            f for f in ['title', 'artist', 'album', 'genre', 'year', 'bpm', 'key_signature', 'comment']
            if file_metadata.get(f) != db_metadata.get(f)
        ]
    elif file_changed:
        action = SyncAction.IMPORT
    elif db_changed:
        action = SyncAction.EXPORT
    else:
        action = SyncAction.SKIP

    return SyncResult(
        track_id=track_id,
        local_path=local_path,
        action=action,
        computed_file_hash=current_hash,
        file_metadata=file_metadata if action != SyncAction.SKIP else None,
        db_metadata=db_metadata,  # For field-level diff display
        conflict_fields=conflict_fields,
    )


def analyze_sync_status(config: Config) -> tuple[list[SyncResult], dict[str, int]]:
    """Analyze all local tracks and determine sync actions needed.

    Side effect: Populates file_metadata_hash for tracks that have NULL hash.
    This enables bootstrap on first run - hashes are computed and stored,
    but only actual changes (not NULL -> hash) trigger import/export.

    Returns:
        Tuple of (list of SyncResult, stats dict with counts by action type)
    """
    # Implementation notes:
    # 1. Query all local tracks with their stored hash and timestamps
    # 2. For each track, call determine_sync_action()
    # 3. If stored_hash was NULL, populate it (bootstrap for that track)
    # 4. Collect results and compute stats
    #
    # No threshold-based bootstrap detection - just populate hash for any
    # track with NULL hash. Simple and predictable.


def execute_sync_actions(
    config: Config,
    results: list[SyncResult],
    strategy: ConflictStrategy = ConflictStrategy.NEWER,
    show_progress: bool = True,
) -> dict[str, int]:
    """Execute determined sync actions.

    For IMPORT: read file metadata, update database, update file_metadata_hash
    For EXPORT: write database metadata to file (requires config for write settings)
    For CONFLICT: resolve based on strategy, then import or export

    Error handling: Failed tracks are logged with logger.exception(),
    counted in stats['failed'], and skipped. Sync continues with remaining tracks.

    Returns stats: {imported, exported, conflicts_resolved, skipped, failed}
    """


def sync_pull(config: Config, force_all: bool = False, dry_run: bool = False) -> dict[str, int]:
    """Import file metadata to database (trust files).

    Args:
        force_all: If True, import all files regardless of hash (bypass change detection)
        dry_run: If True, return stats without making changes

    Returns:
        Stats dict: {imported, failed, skipped} or {to_import} if dry_run
    """


def sync_push(config: Config, force_all: bool = False, dry_run: bool = False) -> dict[str, int]:
    """Export database metadata to files (trust database).

    Args:
        force_all: If True, export all files regardless of change detection
        dry_run: If True, return stats without making changes

    Returns:
        Stats dict: {exported, failed, skipped} or {to_export} if dry_run
    """
```

### Database Helpers

Add batch function to update file_metadata_hash after sync (uses executemany for performance):

```python
def update_tracks_sync_state(updates: list[tuple[int, str]]) -> None:
    """Batch update tracks' file_metadata_hash and last_synced_at after sync.

    Args:
        updates: List of (track_id, file_hash) tuples
    """
    if not updates:
        return

    with get_db_connection() as conn:
        conn.executemany(
            """UPDATE tracks
               SET file_metadata_hash = ?, last_synced_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            [(file_hash, track_id) for track_id, file_hash in updates]
        )
        conn.commit()


def get_track_metadata_from_db(track_id: int) -> dict:
    """Fetch current metadata values from database for conflict detection."""
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT title, artist, album, genre, year, bpm, key_signature, comment
               FROM tracks WHERE id = ?""",
            (track_id,)
        ).fetchone()
        return dict(row) if row else {}
```

### Sync Lock (Prevent Concurrent Syncs)

```python
import fcntl
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def sync_lock(config: Config):
    """Acquire exclusive lock to prevent concurrent syncs.

    Usage:
        with sync_lock(config):
            # sync operations here

    Raises SyncInProgressError if another sync is running.
    """
    lock_path = Path(config.data_dir) / ".sync.lock"
    lock_file = open(lock_path, 'w')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise SyncInProgressError("Another sync is already running")
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
```

### Implementation Notes

**COMMENT extraction verification:** Before relying on COMMENT in hash, verify that
`extract_track_metadata()` correctly extracts COMMENT field for all supported formats:
- MP3 (ID3 COMM frame) ✓
- M4A (©cmt) ✓
- FLAC (COMMENT/DESCRIPTION) - verify
- Opus/Ogg (COMMENT) - verify

**Ping-pong detection:** If a track's `last_sync_direction` alternates repeatedly
(import→export→import), log a warning - this indicates conflicting edits or
a bug in change detection.

## Verification
1. Unit test `compute_metadata_hash()` - verify deterministic output, handles None values
2. Unit test `determine_sync_action()` - test all 4 cases (skip, import, export, conflict)
3. Test with real files: modify BPM externally, verify `analyze_sync_status()` returns IMPORT action
4. Test sync lock: run two syncs simultaneously, verify second one fails gracefully
5. Test COMMENT extraction for FLAC and Opus files
