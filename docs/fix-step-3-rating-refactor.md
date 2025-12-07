# Step 3: Refactor rating.py for Function Length and Type Safety

**Priority**: CRITICAL + IMPORTANT
**File**: `src/music_minion/commands/rating.py`
**Estimated Time**: 20 minutes

## Issues to Fix

### Issue 1: Function Exceeds 20-Line Limit (Lines 674-712)

**Severity**: Critical
**Location**: `_build_coverage_filter_sets()` function

**Problem**:
The function is 39 lines long, violating the project standard of ≤20 lines per function (CLAUDE.md).

**Current Code** (abbreviated):
```python
def _build_coverage_filter_sets(
    source_filter: Optional[str],
    genre_filter: Optional[str],
    year_filter: Optional[int],
    playlist_id: Optional[int],
) -> tuple[RatingCoverageFilters | None, RatingCoverageFilters | None]:
    """Return (library_filters, filter_filters) for coverage queries."""

    library_filters: RatingCoverageFilters = cast(RatingCoverageFilters, {})
    if source_filter and source_filter != "all":
        library_filters["source_filter"] = source_filter

    filter_filters: RatingCoverageFilters = cast(
        RatingCoverageFilters, dict(library_filters)
    )
    if genre_filter:
        filter_filters["genre_filter"] = genre_filter
    if year_filter:
        filter_filters["year_filter"] = year_filter
    if playlist_id:
        filter_filters["playlist_id"] = playlist_id

    library_result = library_filters if library_filters else None
    filter_result = filter_filters if filter_filters else None

    return library_result, filter_result
```

**Fix**: Remove type casts and simplify logic using Optional pattern.

**Expected Result**:
```python
def _build_coverage_filter_sets(
    source_filter: Optional[str],
    genre_filter: Optional[str],
    year_filter: Optional[int],
    playlist_id: Optional[int],
) -> tuple[Optional[RatingCoverageFilters], Optional[RatingCoverageFilters]]:
    """Return (library_filters, filter_filters) for coverage queries.

    library_filters: Only source_filter applied (library-wide scope)
    filter_filters: All filters applied (active filter scope)

    Returns None if no filters are active for that scope.
    """
    # Build library-level filters (source only)
    library_filters: Optional[RatingCoverageFilters] = None
    if source_filter and source_filter != "all":
        library_filters = {"source_filter": source_filter}

    # Build filter-level filters (all filters)
    filter_filters: Optional[RatingCoverageFilters] = None
    if library_filters or genre_filter or year_filter or playlist_id:
        filter_filters = dict(library_filters) if library_filters else {}
        if genre_filter:
            filter_filters["genre_filter"] = genre_filter
        if year_filter:
            filter_filters["year_filter"] = year_filter
        if playlist_id:
            filter_filters["playlist_id"] = playlist_id

    return library_filters, filter_filters
```

---

### Issue 2: Unnecessary Type Casts (Lines 679, 685)

**Severity**: Important
**Location**: Lines 679 and 685 in `_build_coverage_filter_sets()`

**Problem**:
Using `cast(RatingCoverageFilters, {})` to work around type system instead of using proper Optional pattern. This is a code smell and makes intent unclear.

**Current Code**:
```python
library_filters: RatingCoverageFilters = cast(RatingCoverageFilters, {})
# ...
filter_filters: RatingCoverageFilters = cast(
    RatingCoverageFilters, dict(library_filters)
)
```

**Fix**: Already addressed in Issue 1 above - use `Optional[RatingCoverageFilters]` and build dicts directly.

---

## Implementation Steps

1. **Update `_build_coverage_filter_sets()` function**:
   - Open `src/music_minion/commands/rating.py`
   - Navigate to line ~674 where `_build_coverage_filter_sets()` is defined
   - Replace the entire function with the refactored version above

2. **Remove unused import**:
   - Check if `cast` from typing is still used elsewhere in the file
   - If not, remove it from the imports at the top:
     ```python
     from typing import List, Optional, Tuple, cast  # Remove cast if unused
     ```

3. **Update return type annotation**:
   - The return type changes from `tuple[RatingCoverageFilters | None, RatingCoverageFilters | None]`
   - To: `tuple[Optional[RatingCoverageFilters], Optional[RatingCoverageFilters]]`
   - (More readable and follows project conventions)

## Verification

After making changes, verify:

1. **Function length**: Count lines - should be ≤20 lines
2. **No type casts**: Search for `cast(` in the function - should be zero occurrences
3. **Type safety**: File should type-check correctly
4. **Compile check**:
   ```bash
   python -m py_compile src/music_minion/commands/rating.py
   ```

5. **Functional equivalence**: The logic should work identically:
   - If no filters: returns `(None, None)`
   - If source only: returns `({"source_filter": "..."}, {"source_filter": "..."})`
   - If source + genre: returns `({"source_filter": "..."}, {"source_filter": "...", "genre_filter": "..."})`

## Testing

Test the rating comparison feature to ensure coverage stats still work:
```bash
# Start a rating session and verify coverage stats display correctly
music-minion
> rate --count 5
```

Check that:
- Coverage percentages display correctly
- Library-wide stats vs filtered stats are computed correctly
- No type errors or crashes

## References

- Project CLAUDE.md: "Functions: ≤20 lines, ≤3 nesting levels, single purpose"
- Project CLAUDE.md: "Never use: `any`, `unknown` (without type guards), `!` (non-null assertions)"
- PEP 484: Type hints - prefer explicit Optional over cast()
