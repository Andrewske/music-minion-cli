# AI Learnings

> Critical insights and gotchas for working in this codebase. Last cleaned: 2026-02-14

## Gotchas & Pitfalls

### MPV Track Transition Race Condition (CRITICAL)
- **Bug**: `eof-reached` stays True during `loadfile` transitions, causing autoplay loops
- **Wrong**: Checking `eof-reached=True` → triggers autoplay again on new track
- **Right**: Always validate position first: `position >= duration - 0.5`
- **During transition**: MPV reports `eof-reached=True`, `position=0.0`, `duration=30.0` (new track)
- **Files**: `domain/playback/mpv.py`, affects comparison mode and playlist autoplay

### SQLite GROUP_CONCAT Limitations
- `GROUP_CONCAT(DISTINCT column, separator)` fails - SQLite doesn't support both
- Use `GROUP_CONCAT(column, ' ')` OR `GROUP_CONCAT(DISTINCT column)`, never both

### SQLite Threading with FastAPI
- **Error**: `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`
- **Cause**: `async def get_db()` dependency creates connection in different thread
- **Fix**: Use synchronous `def` handlers with inline `with get_db_connection() as conn:`

### Serato Crate Export Path Issues
- `pyserato` hardcodes `SubCrates` (capital C), not `Subcrates`
- `pyserato` calls `Path.resolve()` which treats Windows paths as relative on Linux
- **Fix**: Monkey-patch `PosixPath.resolve()` during save; strip drive letter (Serato adds it)
- `pyserato.model.crate.Crate.tracks` is a `set`, not a list

### State Tracking Tuple Consistency (Analytics Viewer Bug)
- **Bug**: j/k scrolling not working in analytics viewer
- **Cause**: Inconsistent tuple sizes in change detection (7 vs 9 elements)
- **Rule**: Initial value, comparison, and ALL update sites must have matching tuple fields
- State can change, but UI won't redraw without proper change detection

### Emoji Unicode Normalization
- **Always** normalize with `unicodedata.normalize('NFC', emoji_str)` before database ops
- Strip variation selectors: `emoji_str.replace('\ufe0e', '').replace('\ufe0f', '')`

## Architecture Decisions

### Message Queue for Blessed UI Race Conditions
Commands calling `log()` during execution overwrite UIState. Solution: queue messages, drain after command completes.
```python
# core/output.py - Queue with threading lock
_pending_history_messages: list[tuple[str, str]] = []
def log(message, level):
    logger.log(level, message)
    if _blessed_mode_active:
        _pending_history_messages.append((message, color))

# executor.py - Drain AFTER command finishes
ctx, result = handle_command(ctx, cmd, args)
for msg, color in drain_pending_history_messages():
    ui_state = add_history_line(ui_state, msg, color)
```

### Multi-Provider Like Tracking
Use `ratings.source` column to distinguish provider-specific likes from user ratings:
- User ratings: temporal, multiple allowed per track
- Provider likes: binary state, one marker per provider (prevents duplicate API calls)
```python
# Check marker existence before API call
if not has_soundcloud_like(track_id):
    provider.like_track(state, soundcloud_id)
    add_rating(track_id, 'like', context, source='soundcloud')
```

### Stateful WebSocket Broadcasting
Reconnecting clients need current state, not just future events:
```python
class SyncManager:
    current_comparison: dict | None  # Stored in memory
    async def connect(self, ws):
        await ws.accept()
        self.connections.add(ws)
        # Send sync:full with current_comparison immediately
```

## Performance Considerations

### UI State Caching for Database Queries
Cache database flags in UIState to avoid repeated queries during partial renders:
```python
@dataclass
class UIState:
    current_track_has_soundcloud_like: bool = False  # Cached
# Update only during full redraws, partial renders use cached value
```
60+ renders/minute during playback - never query database in render path.

### In-Memory Filtering vs Database LIKE
- Pre-load: 100ms initial load for 5000 tracks (acceptable)
- Filter: <5ms per keystroke vs 20-50ms for database LIKE queries
- **Rule**: For read-heavy ops with <10K records, in-memory filtering wins

### Analytics Pre-Calculation
- **Bug**: Formatting 597 artists on every keystroke caused 100ms+ delays
- **Fix**: Cache total line count in state, reduced keystroke latency from ~100ms to <1ms
- **Rule**: Never re-compute expensive operations in hot paths

## Integration Notes

### Atomic File Operations with Mutagen (CRITICAL)
Mutagen requires target file to exist. Crashes during write corrupt metadata permanently.
```python
temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)  # Copy to temp
    audio = MutagenFile(temp_path)      # Load temp
    audio.save()                         # Save in place (no filename arg!)
    os.replace(temp_path, file_path)    # Atomic
except Exception:
    if os.path.exists(temp_path): os.remove(temp_path)
    raise
```

### Background Thread Silent Logging
Exceptions in threads don't propagate. Must catch and log explicitly.
```python
def _background_worker():
    threading.current_thread().silent_logging = True
    try:
        logger.info("Working...")
    except Exception:
        logger.exception("Failed")  # Stack trace to file
    finally:
        threading.current_thread().silent_logging = False  # ALWAYS reset
```

### File Move Detection Algorithm
Syncthing conflicts + moved files + orphaned records - handled during `sync local`:
1. **Auto-delete Syncthing conflicts** unconditionally (don't check file existence)
2. **Match moved files** by filename + filesize (fast, no metadata extraction)
3. **Path similarity threshold**: 0.8 for auto-relocate (prevents false matches)
4. **Delete orphans** when file not found and no match
- Performance: ~1.5-2s for 5000 tracks (SSD)
- Uses `executemany()` for 30-50x faster batch operations

## Debugging Patterns

### Three-Tier Rendering for blessed UI
Prevents flashing from full redraws:
1. **Full redraw**: Track change, resize, init - clear screen, render everything
2. **Input update**: Typing/filtering - redraw input area only
3. **Partial update**: Clock/progress bar only - position + line clear, no `term.clear()`

State hash excludes volatile data (position) to detect actual changes.

### Data Ownership Before Removal
```python
# NEVER remove without checking source
for tag in tags_to_remove:
    if db_tag_dict.get(tag) == 'file':  # Only remove file-sourced
        remove_tag(track_id, tag)
    # else: Preserve user/AI data
```

### 2026-02-14 - Shared utility for batch emoji fetching

**Pattern**: Consolidated duplicate emoji-fetching code into shared `web/backend/queries/emojis.py`:
```python
def get_emojis_for_tracks_batch(track_ids: list[int], db_conn) -> dict[int, list[str]]:
    # Single query for all tracks instead of N queries
```

**Why it matters**: Initial implementation had each endpoint (comparisons, playlists, radio) fetching emojis separately. Refactoring to shared utility:
- Reduced code duplication across 4 endpoints
- Consistent N+1 prevention pattern
- Single source of truth for emoji batch queries

**Rule**: When adding same data to multiple endpoints, create shared query utility immediately.

### 2026-02-16 - Global state for cross-route UI patterns

**Pattern**: When sidebar content needs to affect multiple routes, use Zustand store instead of props drilling:
```typescript
// stores/filterStore.ts - Global state
export const useFilterStore = create<FilterState>((set) => ({
  filters: [],
  setFilters: (filters) => set({ filters }),
  // ... other actions
}));

// Sidebar component reads/writes store
function FilterSidebar() {
  const { filters, setFilters } = useFilterStore();
}

// Route components consume store
function SomePage() {
  const { filters } = useFilterStore();
  // Apply filters to track list
}
```

**Why it matters**: Initial plan had route-aware sidebar content switching (playlists on home, filters on builder). This required complex props drilling through root layout. Global store allows:
- Sidebar sections always present, independently collapsible
- Filter state persists across route changes
- No props threading through TanStack Router
- Simpler mental model: sidebar is UI chrome, routes consume state

**Rule**: Persistent sidebar/nav content that affects page behavior → use global store, not route-aware rendering.
