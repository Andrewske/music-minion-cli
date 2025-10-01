# Refactoring Circular Imports - Implementation Plan

**Status**: Not Started
**Priority**: Medium
**Effort**: Large (3-5 hours)
**Branch**: Create new branch `refactor/explicit-state-passing` from `refactor/architecture-reorganization`

## Problem Statement

The architecture refactor introduced runtime `sys.modules` imports to work around circular dependencies, violating CLAUDE.md principles:

> **From CLAUDE.md**: "Functional over Classes: Use functions and modules, avoid complex class hierarchies. **CRITICAL**: Always question if a class is necessary - prefer functions with explicit state passing over classes with instance variables."

### Current Anti-Pattern

**helpers.py** (lines 19-23, 117-148):
```python
def get_console():
    """Get Rich Console instance from main module."""
    import sys
    main_module = sys.modules['music_minion.main']
    return main_module.console

def ensure_library_loaded() -> bool:
    """Ensure music library is loaded."""
    import sys
    main_module = sys.modules['music_minion.main']

    if not main_module.music_tracks:
        # ... mutates main_module state
        main_module.music_tracks = [...]
        main_module.current_config = config.load_config()
```

**commands/playback.py** (lines 18-69):
```python
def get_player_state():
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state

def set_player_state(state):
    """Set player state in main module."""
    from .. import main
    main.current_player_state = state

# Repeated in EVERY command file
def get_music_tracks():
    from .. import main
    return main.music_tracks

def get_config():
    from .. import main
    return main.current_config
```

**Risks**:
1. **Runtime dependency**: If `main` module not loaded, crashes with KeyError
2. **Hidden dependencies**: State mutations happen far from where state is defined
3. **Untestable**: Commands cannot be tested without full app initialization
4. **Violates functional principles**: Global mutable state accessed via import hacks

## Proposed Solution: Explicit State Passing

### Phase 1: Create Context Object (1 hour)

**Create `src/music_minion/context.py`:**
```python
"""Application context for explicit state passing."""

from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from rich.console import Console

from .core.config import Config
from .domain.library import Track
from .domain.playback import PlayerState


@dataclass
class AppContext:
    """Immutable application context passed to all functions."""

    # Configuration
    config: Config

    # State
    music_tracks: List[Track]
    player_state: PlayerState

    # UI
    console: Console

    @classmethod
    def create(cls, config: Config) -> 'AppContext':
        """Create initial application context."""
        return cls(
            config=config,
            music_tracks=[],
            player_state=PlayerState(),
            console=Console(),
        )

    def with_tracks(self, tracks: List[Track]) -> 'AppContext':
        """Return new context with updated tracks."""
        return AppContext(
            config=self.config,
            music_tracks=tracks,
            player_state=self.player_state,
            console=self.console,
        )

    def with_player_state(self, state: PlayerState) -> 'AppContext':
        """Return new context with updated player state."""
        return AppContext(
            config=self.config,
            music_tracks=self.music_tracks,
            player_state=state,
            console=self.console,
        )
```

### Phase 2: Update Command Signatures (2 hours)

**Before** (commands/playback.py):
```python
def handle_play_command(args: List[str]) -> bool:
    current_player_state = get_player_state()  # Runtime import hack
    music_tracks = get_music_tracks()
    # ... business logic
    set_player_state(new_state)  # Mutate global state
    return True
```

**After**:
```python
def handle_play_command(ctx: AppContext, args: List[str]) -> tuple[AppContext, bool]:
    """Handle play command with explicit state.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    # Read from context (explicit dependency)
    current_player_state = ctx.player_state
    music_tracks = ctx.music_tracks

    # ... business logic

    # Return new context (immutable update)
    updated_ctx = ctx.with_player_state(new_state)
    return updated_ctx, True
```

**Files to update** (15 files):
- `commands/playback.py` (7 functions)
- `commands/playlist.py` (12 functions)
- `commands/rating.py` (4 functions)
- `commands/ai.py` (3 functions)
- `commands/sync.py` (5 functions)
- `commands/track.py` (3 functions)
- `commands/admin.py` (2 functions)

### Phase 3: Update Router (30 minutes)

**router.py**:
```python
def execute_command(ctx: AppContext, command: str, args: List[str]) -> tuple[AppContext, bool]:
    """Execute command with explicit state passing.

    Returns:
        (updated_context, should_continue)
    """
    if command == 'play':
        return playback.handle_play_command(ctx, args)
    elif command == 'pause':
        return playback.handle_pause_command(ctx)
    # ... etc

    return ctx, True  # No state change
```

### Phase 4: Update Main Loop (30 minutes)

**main.py**:
```python
def interactive_mode() -> None:
    """Main interactive loop with explicit state."""
    # Initialize context
    config = load_config()
    ctx = AppContext.create(config)

    # Load library
    tracks = library.scan_music_library(config, show_progress=True)
    ctx = ctx.with_tracks(tracks)

    # Main loop
    should_continue = True
    while should_continue:
        user_input = input("> ")
        command, args = parse_command(user_input)

        # Execute command and get updated context
        ctx, should_continue = execute_command(ctx, command, args)
```

### Phase 5: Remove helpers.py Hacks (30 minutes)

**Delete or refactor**:
- `helpers.py:get_console()` → Use `ctx.console`
- `helpers.py:ensure_library_loaded()` → Return context from explicit load function
- `helpers.py:auto_export_if_enabled()` → Take context as parameter

**New signatures**:
```python
def ensure_library_loaded(ctx: AppContext) -> AppContext:
    """Ensure music library is loaded, return updated context."""
    if not ctx.music_tracks:
        tracks = library.scan_music_library(ctx.config, show_progress=False)
        return ctx.with_tracks(tracks)
    return ctx

def auto_export_if_enabled(ctx: AppContext, playlist_id: int) -> None:
    """Auto-export playlist using context config."""
    if not ctx.config.playlists.auto_export:
        return
    # ... use ctx.config instead of main_module.current_config
```

### Phase 6: Update UI Integration (1 hour)

**ui/blessed/app.py**:
```python
def run_interactive_ui(ctx: AppContext) -> AppContext:
    """Run interactive UI with explicit state passing.

    Returns:
        Updated context after UI session
    """
    # ... UI event loop
    # Pass context to command handlers
    ctx, should_quit = execute_command(ctx, command_line)
    return ctx
```

## Migration Checklist

**Pre-Migration** (20 minutes):
- [ ] Create new branch `refactor/explicit-state-passing` from `refactor/architecture-reorganization`
- [ ] Run test suite baseline
- [ ] Create backup of current working state

**Phase 1** (1 hour):
- [ ] Create `src/music_minion/context.py` with `AppContext` dataclass
- [ ] Add `with_*()` helper methods for immutable updates
- [ ] Write unit tests for context creation and updates

**Phase 2** (2 hours):
- [ ] Update `commands/playback.py` signatures (7 functions)
- [ ] Update `commands/playlist.py` signatures (12 functions)
- [ ] Update `commands/rating.py` signatures (4 functions)
- [ ] Update `commands/ai.py` signatures (3 functions)
- [ ] Update `commands/sync.py` signatures (5 functions)
- [ ] Update `commands/track.py` signatures (3 functions)
- [ ] Update `commands/admin.py` signatures (2 functions)
- [ ] Remove `get_player_state()`, `set_player_state()`, `get_music_tracks()`, `get_config()` from each file

**Phase 3** (30 minutes):
- [ ] Update `router.py` to accept and return context
- [ ] Update all command dispatch calls

**Phase 4** (30 minutes):
- [ ] Update `main.py` interactive loop
- [ ] Thread context through entire session

**Phase 5** (30 minutes):
- [ ] Refactor `helpers.py` functions to take context
- [ ] Remove all `sys.modules['music_minion.main']` hacks

**Phase 6** (1 hour):
- [ ] Update `ui/blessed/app.py` to use context
- [ ] Update event handlers to pass context
- [ ] Update command execution flow

**Validation** (30 minutes):
- [ ] Run syntax checks: `find src -name "*.py" -exec python -m py_compile {} +`
- [ ] Test CLI starts: `music-minion --help`
- [ ] Test interactive mode
- [ ] Test all commands manually
- [ ] Verify no runtime import errors

**Cleanup** (15 minutes):
- [ ] Remove unused imports
- [ ] Run Ruff formatter
- [ ] Update `ai-learnings.md` with pattern
- [ ] Commit with detailed message

## Benefits

1. **Testability**: Commands can be tested with mock contexts
2. **Type Safety**: IDE autocomplete works, type checkers catch errors
3. **Clarity**: Dependencies are explicit in function signatures
4. **Immutability**: Context updates return new objects, preventing action-at-a-distance bugs
5. **CLAUDE.md Compliance**: Aligns with "explicit state passing" principle

## Risks & Mitigation

**Risk 1: Large surface area** (36 function signatures to change)
- **Mitigation**: Use automated refactoring tools, do one module at a time, test incrementally

**Risk 2: Breaking changes to UI integration**
- **Mitigation**: Update blessed UI in same PR, test interactive mode thoroughly

**Risk 3: Performance overhead from immutable updates**
- **Mitigation**: Context is small (4 fields), Python dataclasses are efficient, negligible overhead

**Risk 4: Merge conflicts with main branch**
- **Mitigation**: Keep refactor branch separate, merge architecture-reorganization first, then this

## Success Criteria

- [ ] Zero `sys.modules` imports in codebase
- [ ] Zero `from .. import main` in command files
- [ ] All commands accept `AppContext` as first parameter
- [ ] All commands return `(AppContext, bool)` tuple
- [ ] CLI fully functional with new pattern
- [ ] Code passes all linting/type checks

## Estimated Timeline

- **Phase 1**: 1 hour
- **Phase 2**: 2 hours
- **Phase 3**: 30 minutes
- **Phase 4**: 30 minutes
- **Phase 5**: 30 minutes
- **Phase 6**: 1 hour
- **Validation**: 30 minutes
- **Total**: ~6 hours (spread over 1-2 days)

## Alternative: Keep Current Pattern

If the refactor is deemed too risky, document the current pattern in `ai-learnings.md`:

```markdown
## State Access Pattern (Pragmatic Compromise)

**Context**: After architecture reorganization, circular imports required runtime module loading.

**Pattern**: Use `sys.modules` to access main module state:
```python
def get_state():
    import sys
    return sys.modules['music_minion.main'].current_state
```

**Trade-offs**:
- ✅ Avoids circular import errors
- ✅ Minimal code changes during refactor
- ❌ Violates explicit state passing principle
- ❌ Makes testing difficult
- ❌ Runtime dependency on module load order

**Recommendation**: Refactor to explicit state passing in future PR (see refactor-circular-imports.md)
```

## Notes

- This refactor is **independent** from the architecture reorganization
- Can be done in a **separate PR** after merging architecture changes
- Aligns codebase with CLAUDE.md functional principles
- Improves long-term maintainability and testability

---

**Created**: 2025-10-01
**Author**: Claude Code Review
**Related**: Architecture Migration (docs/architecture-migration.md)
