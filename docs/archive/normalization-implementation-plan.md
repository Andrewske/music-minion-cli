# Audio Normalization Implementation Plan

## Overview
Add MP3Gain/AACGain normalization to Music Minion with backup system, database tracking, test workflow, and progress reporting.

**User Requirements:**
- Tool: MP3Gain/AACGain (destructive normalization to 92dB)
- Backup: Keep permanently in `~/.local/share/music-minion/normalization_backups/`
- Database: Track normalization status with `normalized_at` timestamp
- Workflow: Test on 10 tracks first, estimate time, then process full library (~5000 tracks)
- Progress: Show real-time progress with time estimates

---

## Implementation Steps

### Step 1: Database Schema Migration (v24 → v25)

**File:** `src/music_minion/core/database.py`

**Changes:**

1. **Update schema version constant** (line 83):
   ```python
   # Change from:
   SCHEMA_VERSION = 24

   # To:
   SCHEMA_VERSION = 25
   ```

2. **Add migration block in `migrate_database()` function** (after line 840, after the v24 migration block):

   ```python
   if current_version < 25:
       # Migration from v24 to v25: Add normalization tracking
       logger.info(
           "Migrating database to schema version 25 (normalization tracking)..."
       )

       # Add normalized_at column to tracks table
       try:
           conn.execute("ALTER TABLE tracks ADD COLUMN normalized_at TIMESTAMP")
       except sqlite3.OperationalError as e:
           if "duplicate column name" not in str(e).lower():
               raise

       # Create index for quick filtering (normalized vs not normalized)
       conn.execute("""
           CREATE INDEX IF NOT EXISTS idx_tracks_normalized
           ON tracks(normalized_at)
       """)

       logger.info("Migration to schema version 25 complete")
       conn.commit()
   ```

**Pattern Reference:** See existing migration blocks at lines 775-840 for the try/except pattern and structure.

---

### Step 2: Create Domain Module for Normalization

**Create new file:** `src/music_minion/domain/audio/__init__.py`

Content: Empty file (standard Python package marker)

**Create new file:** `src/music_minion/domain/audio/normalization.py`

Full implementation:

```python
"""Audio normalization functions using MP3Gain/AACGain."""

from pathlib import Path
import subprocess
import shutil
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def check_aacgain_installed() -> tuple[bool, Optional[str]]:
    """Check if aacgain is installed and return version.

    Returns:
        (is_installed: bool, version_string: Optional[str])
    """
    try:
        result = subprocess.run(
            ["aacgain", "-v"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return True, version
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, None


def create_backup_path(original_path: str, backup_root: Path) -> Path:
    """Generate backup path preserving directory structure.

    Creates path like: backup_root / parent_dir_name / filename

    Args:
        original_path: Absolute path to original file
        backup_root: Root directory for backups

    Returns:
        Path object for backup location
    """
    original = Path(original_path)
    # Use parent directory name + filename to preserve some structure
    relative = Path(original.parent.name) / original.name
    return backup_root / relative


def backup_file(
    source_path: str, backup_root: Path
) -> tuple[bool, Optional[str], Optional[Path]]:
    """Create backup of audio file before normalization.

    Args:
        source_path: Path to file to backup
        backup_root: Root directory for backups

    Returns:
        (success: bool, error_message: Optional[str], backup_path: Optional[Path])
    """
    if not os.path.exists(source_path):
        return False, f"Source file not found: {source_path}", None

    try:
        backup_path = create_backup_path(source_path, backup_root)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file with metadata preservation
        shutil.copy2(source_path, backup_path)

        # Verify backup was created
        if not backup_path.exists():
            return False, "Backup verification failed", None

        return True, None, backup_path

    except Exception as e:
        return False, f"Backup failed: {e}", None


def normalize_file(file_path: str) -> tuple[bool, Optional[str], Optional[dict]]:
    """Normalize audio file using aacgain to 92dB.

    Args:
        file_path: Path to audio file to normalize

    Returns:
        (success: bool, error_message: Optional[str], stats: Optional[dict])
    """
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", None

    try:
        # aacgain -r -k -c -d 3.0: Apply 92dB normalization
        # -r: Track gain (radio mode)
        # -k: Prevent clipping
        # -c: Skip CRC check (faster)
        # -d 3.0: Target 92dB (89dB default + 3dB offset)
        result = subprocess.run(
            ["aacgain", "-r", "-k", "-c", "-d", "3.0", file_path],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout for safety
        )

        if result.returncode != 0:
            return False, f"aacgain failed: {result.stderr}", None

        # Return success with empty stats dict
        return True, None, {}

    except subprocess.TimeoutExpired:
        return False, "Normalization timed out (>60s)", None
    except Exception as e:
        return False, f"Normalization error: {e}", None


def select_test_subset(tracks: list[dict], count: int = 10) -> list[dict]:
    """Select diverse subset of tracks for testing.

    Distributes selection across different file formats (MP3, M4A, Opus)
    to ensure test covers all supported formats.

    Args:
        tracks: List of track dictionaries with 'local_path' key
        count: Number of tracks to select (default: 10)

    Returns:
        List of selected track dictionaries
    """
    if len(tracks) <= count:
        return tracks

    # Group by format for diversity
    by_format = {}
    for track in tracks:
        if not track.get("local_path"):
            continue
        ext = Path(track["local_path"]).suffix.lower()
        if ext not in by_format:
            by_format[ext] = []
        by_format[ext].append(track)

    # Select evenly from each format
    selected = []
    formats = list(by_format.keys())
    per_format = count // len(formats) if formats else count

    for fmt in formats:
        # Sort by duration for consistent selection
        fmt_tracks = sorted(
            by_format[fmt],
            key=lambda t: t.get("duration", 0)
        )
        if len(fmt_tracks) <= per_format:
            selected.extend(fmt_tracks)
        else:
            # Distribute evenly across duration range
            step = len(fmt_tracks) // per_format
            selected.extend(fmt_tracks[i * step] for i in range(per_format))

    # Fill remaining slots if needed
    if len(selected) < count:
        remaining = [t for t in tracks if t not in selected and t.get("local_path")]
        import random
        random.shuffle(remaining)
        selected.extend(remaining[: count - len(selected)])

    return selected[:count]


@dataclass
class NormalizationStats:
    """Statistics from normalization operations."""

    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    backed_up: int = 0
    total_seconds: float = 0.0

    @property
    def avg_seconds_per_track(self) -> float:
        """Calculate average processing time per track."""
        return self.total_seconds / self.total_processed if self.total_processed > 0 else 0.0

    def estimate_remaining_time(self, remaining_tracks: int) -> float:
        """Estimate time remaining for remaining tracks.

        Args:
            remaining_tracks: Number of tracks left to process

        Returns:
            Estimated seconds remaining
        """
        return self.avg_seconds_per_track * remaining_tracks

    def format_time(self, seconds: float) -> str:
        """Format seconds into human-readable time string.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string like "5m 30s" or "2h 15m"
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
```

---

### Step 3: Add Command Handler Functions

**File:** `src/music_minion/commands/admin.py`

**Add imports at the top of the file** (after existing imports):

```python
import time
from datetime import datetime
from pathlib import Path
```

**Add these three functions** (recommended location: after `handle_scan_command()`, around line 357):

```python
def get_tracks_to_normalize(force: bool = False) -> list[dict]:
    """Get tracks that need normalization.

    Args:
        force: If True, return all tracks including already normalized ones

    Returns:
        List of track dictionaries with id, local_path, duration, title, artist
    """
    with get_db_connection() as conn:
        if force:
            # Get all tracks regardless of normalization status
            query = """
                SELECT id, local_path, duration, title, artist
                FROM tracks
                WHERE local_path IS NOT NULL
                ORDER BY artist, album, title
            """
        else:
            # Only get tracks that haven't been normalized
            query = """
                SELECT id, local_path, duration, title, artist
                FROM tracks
                WHERE local_path IS NOT NULL
                  AND normalized_at IS NULL
                ORDER BY artist, album, title
            """

        cursor = conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def run_normalization_batch(
    tracks: list[dict],
    backup_root: Path,
    is_test: bool = False
) -> "NormalizationStats":
    """Process batch of tracks with backup and normalization.

    Args:
        tracks: List of track dictionaries to process
        backup_root: Root directory for backups
        is_test: If True, this is a test run

    Returns:
        NormalizationStats object with processing results
    """
    from music_minion.domain.audio.normalization import (
        backup_file,
        normalize_file,
        NormalizationStats,
    )

    stats = NormalizationStats()
    start_time = time.time()

    total = len(tracks)
    progress_interval = max(1, total // 100)  # Report every 1%
    db_updates = []  # List of (normalized_at, track_id) tuples

    for i, track in enumerate(tracks, 1):
        track_id = track["id"]
        local_path = track.get("local_path")

        # Skip tracks without local files
        if not local_path or not os.path.exists(local_path):
            stats.total_processed += 1
            stats.failed += 1
            continue

        # Create readable track name for logging
        track_name = f"{track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}"

        # STEP 1: BACKUP
        backup_success, backup_error, backup_path = backup_file(local_path, backup_root)
        if not backup_success:
            log(f"  ❌ Backup failed for {track_name}: {backup_error}", level="error")
            stats.total_processed += 1
            stats.failed += 1
            continue

        stats.backed_up += 1

        # STEP 2: NORMALIZE
        norm_success, norm_error, norm_stats = normalize_file(local_path)

        stats.total_processed += 1

        if norm_success:
            stats.successful += 1
            db_updates.append((datetime.now().isoformat(), track_id))
        else:
            stats.failed += 1
            log(f"  ❌ Normalization failed for {track_name}: {norm_error}", level="error")

        # STEP 3: PROGRESS REPORTING (every 1%)
        if i % progress_interval == 0 or i == total:
            percent = (i * 100) // total
            elapsed = time.time() - start_time
            stats.total_seconds = elapsed

            if stats.total_processed > 0:
                remaining = total - i
                est = stats.estimate_remaining_time(remaining)

                log(
                    f"  Progress: {percent}% ({i}/{total}) | "
                    f"✅ {stats.successful} ❌ {stats.failed} | "
                    f"⏱️  ~{stats.format_time(est)} remaining"
                )

    # STEP 4: BATCH UPDATE DATABASE
    if db_updates:
        with get_db_connection() as conn:
            conn.executemany(
                "UPDATE tracks SET normalized_at = ? WHERE id = ?",
                db_updates
            )
            conn.commit()

    stats.total_seconds = time.time() - start_time
    return stats


def handle_normalize_command(
    ctx: AppContext, args: list[str]
) -> tuple[AppContext, bool]:
    """Handle normalize command - normalize audio files to 92dB.

    Command modes:
        normalize             - Full library with test phase (recommended)
        normalize --test      - Test mode only (10 tracks, show estimate)
        normalize --skip-test - Skip test, run immediately on full library
        normalize --force     - Re-normalize all tracks (including already normalized)

    Args:
        ctx: Application context
        args: Command line arguments

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.domain.audio.normalization import (
        check_aacgain_installed,
        select_test_subset,
    )

    # Parse command line arguments
    test_only = "--test" in args
    skip_test = "--skip-test" in args
    force = "--force" in args

    # STEP 1: Check if aacgain is installed
    is_installed, version = check_aacgain_installed()
    if not is_installed:
        log("❌ Error: aacgain not installed", level="error")
        log("Install with: sudo pacman -S aacgain")
        log("Or: sudo apt install aacgain (Ubuntu)")
        log("Or: brew install aacgain (macOS)")
        return ctx, True

    log(f"✓ aacgain detected: {version}")

    # STEP 2: Setup backup directory
    backup_root = ctx.config.get_data_dir() / "normalization_backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    log(f"📁 Backup directory: {backup_root}")

    # STEP 3: Get tracks to normalize
    tracks = get_tracks_to_normalize(force=force)

    if not tracks:
        if force:
            log("✓ All tracks already normalized")
        else:
            log("✓ No tracks need normalization")
        return ctx, True

    log(f"Found {len(tracks)} track(s) to normalize")

    # STEP 4: TEST PHASE (unless --skip-test)
    if not skip_test:
        test_tracks = select_test_subset(tracks, count=min(10, len(tracks)))
        log(f"\n🧪 TEST PHASE: Processing {len(test_tracks)} tracks...")

        test_stats = run_normalization_batch(test_tracks, backup_root, is_test=True)

        log("\n📊 Test Results:")
        log(f"  ✅ Successful: {test_stats.successful}/{test_stats.total_processed}")
        log(f"  ❌ Failed: {test_stats.failed}")
        log(f"  ⏱️  Average: {test_stats.avg_seconds_per_track:.1f}s per track")

        if test_stats.successful == 0:
            log("\n❌ Test failed - no tracks successfully normalized", level="error")
            log("Check aacgain installation and file permissions")
            return ctx, True

        # Show estimate for full library
        if not test_only:
            remaining = len(tracks) - len(test_tracks)
            est_time = test_stats.estimate_remaining_time(remaining)

            log(f"\n📈 Full library estimate:")
            log(f"  Remaining: {remaining} tracks")
            log(f"  Estimated time: ~{test_stats.format_time(est_time)}")

            # Ask for confirmation in CLI mode (not in blessed UI)
            if not hasattr(ctx, 'ui_state') or ctx.ui_state is None:
                response = input("\n⚠️  Proceed with full normalization? [y/N]: ")
                if response.strip().lower() != "y":
                    log("Cancelled by user")
                    return ctx, True

    # If test-only mode, exit here
    if test_only:
        log("\n✓ Test complete")
        log("Run 'normalize' without --test to process full library")
        return ctx, True

    # STEP 5: FULL NORMALIZATION RUN
    log(f"\n🚀 FULL NORMALIZATION: Processing {len(tracks)} tracks to 92dB")

    full_stats = run_normalization_batch(tracks, backup_root, is_test=False)

    # STEP 6: Show final results
    log("\n✅ Normalization Complete!")
    log(f"  ✅ Successful: {full_stats.successful}/{full_stats.total_processed}")
    log(f"  ❌ Failed: {full_stats.failed}")
    log(f"  💾 Backed up: {full_stats.backed_up} files")
    log(f"  ⏱️  Total time: {full_stats.format_time(full_stats.total_seconds)}")
    log(f"  📁 Backups saved to: {backup_root}")

    return ctx, True
```

---

### Step 4: Register Command in Router

**File:** `src/music_minion/router.py`

**Change 1:** Add to `handle_command()` function (around line 250, with other command routing):

```python
elif command == "normalize":
    return admin.handle_normalize_command(ctx, args)
```

**Change 2:** Add to help text (around line 50, in the help text list):

```python
  normalize [opts]  Normalize audio to 92dB (--test --skip-test --force)
```

---

## Command Usage Examples

```bash
# Test mode only - process 10 tracks and show estimate
music-minion normalize --test

# Full library with test phase (RECOMMENDED)
# Tests 10 tracks, shows estimate, asks for confirmation, then processes all
music-minion normalize

# Skip test phase, run immediately on full library
music-minion normalize --skip-test

# Re-normalize ALL tracks including already normalized ones
music-minion normalize --force

# Combine flags - test re-normalization on 10 tracks
music-minion normalize --test --force
```

---

## Implementation Checklist

- [ ] **Step 1:** Update `src/music_minion/core/database.py`
  - [ ] Change `SCHEMA_VERSION = 24` to `25`
  - [ ] Add v25 migration block in `migrate_database()`

- [ ] **Step 2:** Create domain module
  - [ ] Create `src/music_minion/domain/audio/__init__.py` (empty)
  - [ ] Create `src/music_minion/domain/audio/normalization.py` with all functions

- [ ] **Step 3:** Update `src/music_minion/commands/admin.py`
  - [ ] Add imports (time, datetime, Path)
  - [ ] Add `get_tracks_to_normalize()` function
  - [ ] Add `run_normalization_batch()` function
  - [ ] Add `handle_normalize_command()` function

- [ ] **Step 4:** Update `src/music_minion/router.py`
  - [ ] Add command routing for "normalize"
  - [ ] Add to help text

- [ ] **Step 5:** Test the implementation
  - [ ] Install aacgain: `sudo pacman -S aacgain`
  - [ ] Run migration: `music-minion migrate`
  - [ ] Test mode: `music-minion normalize --test`
  - [ ] Verify backups created
  - [ ] Check database updated
  - [ ] Listen to normalized tracks
  - [ ] Full run on small playlist

---

## Testing Verification

### 1. Install aacgain
```bash
sudo pacman -S aacgain  # Arch Linux
# OR
sudo apt install aacgain  # Ubuntu/Debian
# OR
brew install aacgain  # macOS
```

### 2. Run database migration
```bash
music-minion migrate
```

### 3. Test mode (10 tracks)
```bash
music-minion normalize --test
```

**Expected output:**
```
✓ aacgain detected: aacgain v2.0
📁 Backup directory: /home/kevin/.local/share/music-minion/normalization_backups
Found 5000 track(s) to normalize

🧪 TEST PHASE: Processing 10 tracks...
  Progress: 100% (10/10) | ✅ 10 ❌ 0 | ⏱️ ~0s remaining

📊 Test Results:
  ✅ Successful: 10/10
  ❌ Failed: 0
  ⏱️  Average: 2.3s per track

✓ Test complete
Run 'normalize' without --test to process full library
```

### 4. Verify backups created
```bash
ls -la ~/.local/share/music-minion/normalization_backups/
```

### 5. Check database updated
```bash
sqlite3 ~/.local/share/music-minion/music_minion.db \
  "SELECT COUNT(*) FROM tracks WHERE normalized_at IS NOT NULL"
```

**Expected:** Should show 10 (number of test tracks processed)

### 6. Manual listening test
Play a few normalized tracks to verify they sound correct and volume is consistent.

### 7. Full library run
```bash
music-minion normalize
```

**Expected flow:**
1. Test phase processes 10 tracks
2. Shows estimate (e.g., "~3h 15m")
3. Asks for confirmation
4. Processes all tracks with progress updates
5. Shows final stats

---

## Error Handling & Edge Cases

### Missing aacgain
**Symptom:** Command exits with error message
**Solution:** Shows install instructions for different package managers

### Disk space issues
**Symptom:** Backup fails partway through
**Solution:** Error logged, processing continues, failed tracks tracked

### Permission errors
**Symptom:** Can't write to music files
**Solution:** Error logged per track, continues with others

### Interrupted processing (Ctrl+C)
**Behavior:**
- Already-processed tracks have `normalized_at` set in database
- Re-running skips these tracks automatically
- Backups already created remain in place

### Already normalized tracks
**Default behavior:** Skipped (WHERE `normalized_at IS NULL`)
**Force mode:** Re-processes all tracks (creates new backups)

---

## Architecture Notes

### Functional Programming Patterns
- All normalization functions are pure (no side effects except I/O)
- State passed explicitly via function parameters
- Returns values instead of modifying globals
- Immutable dataclass for statistics

### Batch Processing Pattern
- Follows existing pattern from `sync_metadata_export()` in `domain/sync/engine.py`
- Progress reporting: `max(1, total // 100)` for 1% intervals
- Single database transaction at end for performance
- Uses `executemany()` for batch updates

### Error Handling Pattern
- Individual track failures don't stop batch processing
- Errors logged with `log()` from `music_minion.core.output`
- Failed tracks tracked in stats, not marked as normalized
- Summary shown at end

### Command Handler Pattern
- Follows pattern from `handle_scan_command()` in `admin.py`
- Signature: `(AppContext, list[str]) -> tuple[AppContext, bool]`
- Returns updated context (though not modified in this case)
- Returns `True` for should_continue (keeps CLI running)

---

## Performance Estimates

**Per-track processing time:**
- Backup: ~0.1-0.5s (depends on file size)
- Normalization: ~1-3s (depends on file size and codec)
- **Total: ~1.5-3.5s per track**

**For 5000 tracks:**
- Best case: ~2 hours
- Average case: ~3-4 hours
- Worst case: ~5 hours

**Disk space required:**
- Equal to current library size (temporarily)
- Can delete backups after verification
- Recommended: Keep backups for 1-2 weeks

---

## Summary

**Total code changes:**
- New files: 2 (domain module + `__init__`)
- Modified files: 3 (database.py, admin.py, router.py)
- Lines added: ~400
- Database changes: 1 column + 1 index

**Features implemented:**
- ✅ Database tracking of normalization status
- ✅ Permanent backup system with directory preservation
- ✅ Test workflow with time estimation
- ✅ Progress reporting with real-time estimates
- ✅ Batch database updates for performance
- ✅ Multiple command modes (test, skip-test, force)
- ✅ Error handling with detailed logging
- ✅ Follows existing codebase patterns
