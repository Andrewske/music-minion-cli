# Step 5: Standardize Type Hints Across Codebase

**Priority**: SUGGESTION (Code Quality)
**Files**: Multiple files across the codebase
**Estimated Time**: 30-45 minutes

## Overview

The codebase currently mixes old-style type hints (`List`, `Dict`, `Tuple` from `typing`) with modern Python 3.9+ type hints (`list`, `dict`, `tuple`). This inconsistency makes the codebase harder to read and maintain.

**Goal**: Standardize on modern type hints throughout the codebase.

## Background

- **Old-style** (Python 3.5-3.8): `from typing import List, Dict, Tuple, Optional`
- **Modern** (Python 3.9+): Use built-in `list`, `dict`, `tuple` directly, only import `Optional` from `typing`

**Example**:
```python
# Old-style
from typing import List, Dict, Optional
def get_tracks() -> List[Dict[str, Any]]:
    ...

# Modern (preferred)
from typing import Optional, Any
def get_tracks() -> list[dict[str, Any]]:
    ...
```

## Files to Update

### High Priority Files (Modified in recent commit)

1. **src/music_minion/core/database.py**
   - Already partially fixed in Step 4, but may have more instances
   - Search for: `List[`, `Dict[`, `Tuple[`, `Set[`

2. **src/music_minion/commands/rating.py**
   - Already partially fixed in Step 3
   - Search for: `List[`, `Dict[`, `Tuple[`

3. **src/music_minion/commands/playback.py**
   - Check for consistency after Step 2 changes
   - Search for: `Tuple[`

4. **src/music_minion/commands/admin.py**
   - Modified in recent commit
   - Check for old-style hints

### Medium Priority Files (Related modules)

5. **src/music_minion/domain/playback/*.py**
6. **src/music_minion/domain/rating/*.py**
7. **src/music_minion/ui/blessed/*.py**
8. **src/music_minion/commands/*.py** (all command files)

## Implementation Strategy

### Step 1: Find All Occurrences

Run search commands to find old-style type hints:

```bash
# Find all files with old-style List
grep -r "from typing import.*List" src/music_minion/ | cut -d: -f1 | sort -u

# Find all files with old-style Dict
grep -r "from typing import.*Dict" src/music_minion/ | cut -d: -f1 | sort -u

# Find all files with old-style Tuple
grep -r "from typing import.*Tuple" src/music_minion/ | cut -d: -f1 | sort -u

# Find all files with old-style Set
grep -r "from typing import.*Set" src/music_minion/ | cut -d: -f1 | sort -u
```

### Step 2: Create a Replacement Script (Optional)

For bulk replacement, you can use this sed script:

```bash
#!/bin/bash
# replace-type-hints.sh

for file in $(find src/music_minion -name "*.py"); do
    # Replace type hints in code
    sed -i 's/List\[/list\[/g' "$file"
    sed -i 's/Dict\[/dict\[/g' "$file"
    sed -i 's/Tuple\[/tuple\[/g' "$file"
    sed -i 's/Set\[/set\[/g' "$file"

    # Update imports (remove List, Dict, Tuple, Set from typing imports)
    # Note: This is a simplified approach - manual review recommended
done
```

**WARNING**: Automated replacement can break things. Manual review is recommended.

### Step 3: Manual Update Process (Recommended)

For each file:

1. **Update type annotations**:
   ```python
   # Before
   def get_items() -> List[Dict[str, Any]]:

   # After
   def get_items() -> list[dict[str, Any]]:
   ```

2. **Update imports**:
   ```python
   # Before
   from typing import List, Dict, Tuple, Optional, Any

   # After
   from typing import Optional, Any
   ```

3. **Keep from typing**:
   - `Optional` - still needed
   - `Any` - still needed
   - `Union` - still needed (or use `|` syntax)
   - `Callable` - still needed
   - `TypeVar` - still needed
   - Custom types like `TypedDict`, `NamedTuple` - still needed

4. **Verify**:
   ```bash
   python -m py_compile <file>
   ```

## Detailed Examples

### Example 1: database.py

**Before**:
```python
from typing import List, Dict, Optional, Any

def get_tracks() -> List[Dict[str, Any]]:
    """Get all tracks."""
    return [{"id": 1, "title": "Song"}]

def get_track_ids() -> List[int]:
    """Get track IDs."""
    return [1, 2, 3]
```

**After**:
```python
from typing import Optional, Any

def get_tracks() -> list[dict[str, Any]]:
    """Get all tracks."""
    return [{"id": 1, "title": "Song"}]

def get_track_ids() -> list[int]:
    """Get track IDs."""
    return [1, 2, 3]
```

### Example 2: Functions returning tuples

**Before**:
```python
from typing import Tuple, Optional

def parse_track(data: str) -> Tuple[str, Optional[int]]:
    return "title", None
```

**After**:
```python
from typing import Optional

def parse_track(data: str) -> tuple[str, Optional[int]]:
    return "title", None
```

### Example 3: Complex nested types

**Before**:
```python
from typing import List, Dict, Tuple, Optional

def get_playlist_data() -> List[Tuple[int, Dict[str, str]]]:
    return [(1, {"name": "Rock"})]
```

**After**:
```python
def get_playlist_data() -> list[tuple[int, dict[str, str]]]:
    return [(1, {"name": "Rock"})]
```

## Verification

After updating each file:

1. **Syntax check**:
   ```bash
   python -m py_compile src/music_minion/**/*.py
   ```

2. **Type check** (if using mypy):
   ```bash
   mypy src/music_minion/
   ```

3. **Import check** - verify no unused imports:
   ```bash
   # Use ruff or similar
   ruff check --select F401 src/music_minion/
   ```

4. **Run tests**:
   ```bash
   pytest tests/
   ```

## Files by Priority

### Must Update (touched in recent commit):
- [ ] `src/music_minion/core/database.py`
- [ ] `src/music_minion/commands/rating.py`
- [ ] `src/music_minion/commands/playback.py`
- [ ] `src/music_minion/commands/admin.py`
- [ ] `src/music_minion/domain/playback/player.py`

### Should Update (frequently used):
- [ ] `src/music_minion/domain/rating/database.py`
- [ ] `src/music_minion/domain/library.py`
- [ ] `src/music_minion/ui/blessed/state.py`
- [ ] `src/music_minion/commands/sync.py`

### Nice to Update (rest of codebase):
- [ ] All other `.py` files in `src/music_minion/`

## References

- PEP 585: Type Hinting Generics In Standard Collections (Python 3.9+)
- PEP 604: Allow writing union types as `X | Y` (Python 3.10+)
- Project CLAUDE.md: "Type hints required for parameters and returns"

## Notes

- This is a **suggestion-level** task for code quality
- Can be done incrementally over time
- Prioritize files that are frequently modified
- Good opportunity to also check for missing type hints while updating
- Consider adding a pre-commit hook or linter rule to enforce modern type hints going forward
