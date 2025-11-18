## 2025-11-16 12:30

### Changes
- ADDED: Interactive track search with real-time filtering (< 5ms for 5000+ tracks)
- ADDED: Sequential 3-mode UI (Search → Detail → Action)
- ADDED: Quick action shortcuts (p=play, a=add to playlist, e=edit metadata)
- ADDED: Multi-field search (title, artist, album, genre, tags, notes)
- ADDED: `get_all_tracks_with_metadata()` database function with optimized JOIN query
- ADDED: Track search components (`track_search.py`, `search_handlers.py`)
- FIXED: SQLite GROUP_CONCAT error (DISTINCT + separator not supported)
- CHANGED: In-memory filtering instead of database queries for instant results

### LEARNINGS
- In-memory filtering (< 5ms) beats database LIKE queries (20-50ms) for < 10K records
- SQLite's GROUP_CONCAT doesn't support both DISTINCT and custom separator
- UI action protocol (`ctx.with_ui_action()`) is correct pattern for command → UI communication
- Pre-loading data once (100ms) acceptable for instant subsequent filtering

---

## 2025-10-05 20:11

### Changes
- ADDED: Interactive metadata editor with live text input
- ADDED: Add/delete functionality for notes and tags
- FIXED: Editor rendering (layout calculation missing editor_visible check)
- FIXED: Pending changes counter now shows accurate count
- ADDED: Input validation for year and BPM fields

### LEARNINGS
- Modal visibility must be checked in calculate_layout() for proper height allocation
- When editor_visible=True but layout doesn't allocate height, render functions early-return (height <= 0)
- Full redraw logic requires checking modal state changes BEFORE entering partial update blocks

---

## 2025-10-05 16:30

### Changes
- FIXED: Analytics viewer j/k scrolling not working due to state tracking bug
- FIXED: Inconsistent palette_state tuple sizes prevented scroll detection
- CHANGED: Pass analytics_viewer_height separately from palette_height
- CHANGED: Made all palette_state tuples consistent (9 elements)

### LEARNINGS
- State tracking tuples must be consistent across all code paths
- Missing fields in comparison prevents change detection
- Scroll offset changes in state but UI won't redraw without change detection
- Initial value (line 298), comparison (line 338), and updates (lines 422, 485) must match

---

## 2025-10-05 11:30

### Changes
- ADDED: Playlist analytics command with 9 comprehensive metrics
- ADDED: SQL-optimized analytics functions for efficient aggregation
- FIXED: NoneType error in tag confidence formatting
- CHANGED: Genre display limited to top 10
- CHANGED: Output formatting reduced vertical spacing by 40%

### LEARNINGS
- SQL aggregates 10-100x faster than loading tracks
- Harmonic key compatibility requires Camelot wheel mapping
- Blessed UI requires compact output for non-scrollable history

---

## 2025-10-05 15:45

### Changes
- ADDED: Full-screen analytics viewer with keyboard navigation
- ADDED: ASCII bar charts for distributions
- ADDED: Color-coded quality metrics with visual indicators
- ADDED: Scrollable command history with keyboard shortcuts
- CHANGED: Analytics from command history to modal viewer
- CHANGED: Layout calculation for dynamic viewer height
- FIXED: Analytics viewer frozen keyboard (pre-calculation)
- FIXED: Terminal compatibility (removed dim attribute)

### LEARNINGS

#### Performance: Pre-calculate Expensive Operations
**Problem**: Formatting 597 artists on every keystroke caused 100ms+ delays.

**Solution**: Pre-calculate total line count once when opening viewer, cache in state, use cached value in keyboard handler instead of re-formatting.

```python
# In show_analytics_viewer():
all_lines = format_analytics_lines(analytics_data, term)
total_lines = len(all_lines)  # Cache expensive computation
# Store total_lines in state

# In keyboard handler:
max_scroll = max(0, state.analytics_viewer_total_lines - height)
```

**Impact**: Reduced keystroke latency from ~100ms to <1ms.

**Pattern**: Never re-compute expensive operations in event loops. Pre-compute once and cache in state.

---

#### UX: Full-Screen Modal Viewers for Complex Data
**Problem**: Long analytics output in command history was unreadable (squished, can't scroll).

**Solution**: Created dedicated full-screen viewer with:
- Keyboard navigation (j/k/q)
- Scrolling with position indicator
- Dynamic height (uses most of screen)
- Visual hierarchy (colors, charts)

**Pattern**: For data exceeding ~10 lines, create dedicated modal viewer rather than printing to command history.

---

#### Visual Design: ASCII Charts + Color Coding
**Solution**: Combined ASCII bars with color coding for immediate visual recognition:

```python
bar = '▓' * filled_width + '░' * empty_width
color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
```

**Impact**: Instant identification of trends, peaks, and quality issues.

**Pattern**: ASCII visualization provides significant UX improvement with minimal code complexity.

---

#### Terminal Compatibility
**Learning**: Not all terminals support all text attributes. Stick to basics (bold, colors) or implement fallbacks. Alacritty doesn't support `dim` attribute.

---

#### State Management: Immutable Updates with Caching
**Pattern**:
1. Calculate expensive values once when state changes
2. Store in state fields (not recomputed on render)
3. Use cached values in hot paths
4. Clear cache when source data changes

**Critical**: Update cache whenever source data changes to avoid stale values.
