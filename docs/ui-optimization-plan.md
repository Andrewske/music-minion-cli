# UI Optimization Plan

## Overview

The music-minion-cli UI has grown significantly in complexity, with several components becoming difficult to maintain. This plan outlines targeted optimizations to reduce complexity by ~40% while maintaining all functionality and improving maintainability.

## Current Complexity Analysis

### File Sizes (Lines of Code)
- `state.py` - 1,500 lines (Monolithic state management)
- `keyboard.py` - 1,486 lines (Complex input handling)
- `app.py` - 1,172 lines (Massive event loop)
- `dashboard.py` - 612 lines (Complex rendering)
- `comparison.py` - 579 lines (Modal logic)
- **Total: 9,833 lines** across UI components

### Key Issues Identified

1. **Monolithic State Management**: Single UIState class with 50+ fields mixing concerns
2. **Massive Event Loop**: Single `main_loop` function handling rendering, polling, input, IPC
3. **Complex Keyboard Handling**: Single massive function with 20+ conditional branches
4. **Code Duplication**: Scrolling, selection, and modal patterns repeated across components
5. **Mixed Responsibilities**: UI state, modal state, navigation state, and business logic all mixed

## Optimization Strategy

### Phase 1: Extract Common Patterns (High Impact, Low Risk)

#### 1.1 Generic Scrollable List Component

**Problem**: Scrolling logic duplicated across `track_viewer`, `palette`, `analytics_viewer`

**Solution**: Create reusable `ScrollableList` abstraction

```python
# ui/components/scrollable_list.py
@dataclass
class SelectionState:
    selected: int = 0
    scroll: int = 0
    
    def move(self, delta: int, visible_items: int, total_items: int) -> 'SelectionState':
        new_selected = (self.selected + delta) % total_items
        new_scroll = self._adjust_scroll(new_selected, visible_items, total_items)
        return replace(self, selected=new_selected, scroll=new_scroll)

class ScrollableList:
    def __init__(self, items, visible_height, header_lines=2, footer_lines=1):
        self.items = items
        self.state = SelectionState()
        self.visible_height = visible_height - header_lines - footer_lines
        
    def render(self, term, y, selected_formatter=None):
        # Generic scrolling and selection rendering
        pass
        
    def handle_input(self, event):
        # Generic arrow/page navigation
        pass
```

**Files to modify**:
- `components/track_viewer.py` (317 lines)
- `components/palette.py` (419 lines) 
- `components/analytics_viewer.py` (310 lines)

#### 1.2 Generic Modal System

**Problem**: Modal rendering patterns similar but implemented separately

**Solution**: Create common modal abstraction

```python
# ui/components/modal.py
class Modal:
    def __init__(self, title, content_height):
        self.title = title
        self.content_height = content_height
        
    def render_frame(self, term, y):
        # Common modal border/title rendering
        pass
        
def render_overlay(term, state, y, height, renderer):
    """Common overlay rendering with proper clearing."""
    if height <= 0:
        return
    
    # Clear overlay area
    for i in range(height):
        sys.stdout.write(term.move_xy(0, y + i) + term.clear_eol)
    
    # Render content
    renderer(term, state, y, height)
```

#### 1.3 Extract Navigation Patterns

**Problem**: Selection management repeated in multiple components

**Solution**: Create navigation mixins

```python
# ui/mixins/navigation.py
class NavigationMixin:
    def handle_arrows(self, state, event, selection_state):
        if event['type'] == 'arrow_up':
            return selection_state.move(-1, self.visible_items, self.total_items)
        elif event['type'] == 'arrow_down':
            return selection_state.move(1, self.visible_items, self.total_items)
        # ...
```

### Phase 2: Split State Management (Medium Impact, Medium Risk)

#### 2.1 Modular State Architecture

**Problem**: Monolithic `state.py` with 50+ fields and 50+ helper functions

**Solution**: Split into focused modules

```
ui/state/
├── base.py          # Core UIState with essential fields only
├── modals.py        # Modal-specific state (palette, wizard, viewer, etc.)
├── navigation.py    # Selection/scroll state
├── input.py         # Input/history state
└── comparison.py    # Comparison mode state
```

**New Structure**:

```python
# ui/state/base.py
@dataclass
class UIState:
    # Core UI state only
    history: list[tuple[str, str]] = field(default_factory=list)
    history_scroll: int = 0
    feedback_message: Optional[str] = None
    feedback_time: Optional[float] = None
    
    # Composition instead of inheritance
    modal_state: ModalState = field(default_factory=ModalState)
    navigation_state: NavigationState = field(default_factory=NavigationState)
    input_state: InputState = field(default_factory=InputState)

# ui/state/modals.py  
@dataclass
class ModalState:
    active_modal: Optional[str] = None  # 'palette', 'wizard', 'viewer', etc.
    modal_data: dict[str, Any] = field(default_factory=dict)
    
    def show_modal(self, modal_type: str, data: dict) -> 'ModalState':
        return replace(self, active_modal=modal_type, modal_data=data)
        
    def hide_modal(self) -> 'ModalState':
        return replace(self, active_modal=None, modal_data={})

# ui/state/navigation.py
@dataclass
class NavigationState:
    palette_selection: SelectionState = field(default_factory=SelectionState)
    track_viewer_selection: SelectionState = field(default_factory=SelectionState)
    search_selection: SelectionState = field(default_factory=SelectionState)
    # ...
```

#### 2.2 Simplify State Update Functions

**Problem**: 50+ repetitive helper functions for simple state transitions

**Solution**: Generic update system

```python
# ui/state/updaters.py
class StateUpdater:
    @staticmethod
    def update_selection(state: UIState, component: str, delta: int) -> UIState:
        # Generic selection update logic
        pass
        
    @staticmethod
    def update_modal(state: UIState, modal_type: str, data: dict) -> UIState:
        # Generic modal update logic
        pass
```

### Phase 3: Mode-Based Keyboard Handling (High Impact, Medium Risk)

#### 3.1 Handler System Architecture

**Problem**: Single massive `handle_key` function with 20+ conditional branches

**Solution**: Mode-based handler system

```python
# ui/handlers/keyboard.py
class KeyboardHandler:
    def __init__(self):
        self.mode_handlers = {
            'normal': NormalModeHandler(),
            'palette': PaletteModeHandler(),
            'wizard': WizardModeHandler(),
            'track_viewer': TrackViewerHandler(),
            'comparison': ComparisonModeHandler(),
            'analytics_viewer': AnalyticsViewerHandler(),
            'metadata_editor': MetadataEditorHandler(),
        }
    
    def handle_key(self, state: UIState, key: Keystroke) -> tuple[UIState, Optional[dict]]:
        mode = self._detect_mode(state)
        handler = self.mode_handlers[mode]
        return handler.handle(state, key)
    
    def _detect_mode(self, state: UIState) -> str:
        if state.modal_state.active_modal:
            return state.modal_state.active_modal
        return 'normal'

# ui/handlers/modes/base.py
class BaseModeHandler:
    def handle(self, state: UIState, key: Keystroke) -> tuple[UIState, Optional[dict]]:
        event = self._parse_key(key)
        return self._handle_event(state, event)
    
    def _parse_key(self, key: Keystroke) -> dict:
        # Common key parsing logic
        pass
    
    @abstractmethod
    def _handle_event(self, state: UIState, event: dict) -> tuple[UIState, Optional[dict]]:
        pass
```

#### 3.2 Extract Common Patterns

**Problem**: Repetitive key parsing and mode handling

**Solution**: Common mixins and base classes

```python
# ui/handlers/mixins.py
class NavigationMixin:
    def handle_navigation_keys(self, state: UIState, event: dict, selection_key: str):
        if event['type'] == 'arrow_up':
            return self._move_selection(state, selection_key, -1)
        elif event['type'] == 'arrow_down':
            return self._move_selection(state, selection_key, 1)
        # ...

class ModalMixin:
    def handle_modal_keys(self, state: UIState, event: dict):
        if event['type'] == 'escape':
            return state.modal_state.hide_modal(), None
        # ...
```

### Phase 4: System-Based Event Loop (High Impact, High Risk)

#### 4.1 Extract Focused Systems

**Problem**: Massive `main_loop` function handling rendering, polling, input, IPC

**Solution**: Split into focused systems

```python
# ui/systems/rendering.py
class RenderSystem:
    def __init__(self):
        self.cache = RenderCache()
    
    def render(self, ctx: AppContext, ui_state: UIState) -> None:
        dirty_regions = self._calculate_dirty_regions(ui_state, self.cache)
        
        if dirty_regions:
            self._render_regions(ctx, ui_state, dirty_regions)
            self._update_cache(ui_state)

# ui/systems/polling.py  
class PollingSystem:
    def __init__(self):
        self.pollers = [
            PlayerPoller(interval=10),
            ScanPoller(interval=5),
            SyncPoller(interval=5),
            ConversionPoller(interval=5),
        ]
        self.frame_count = 0
    
    def update(self, ctx: AppContext, ui_state: UIState) -> tuple[AppContext, UIState]:
        for poller in self.pollers:
            if self.frame_count % poller.interval == 0:
                ctx, ui_state = poller.poll(ctx, ui_state)
        return ctx, ui_state

# ui/systems/input.py
class InputSystem:
    def __init__(self, keyboard_handler: KeyboardHandler):
        self.keyboard_handler = keyboard_handler
    
    def handle_input(self, term: Terminal, ui_state: UIState) -> tuple[UIState, Optional[dict]]:
        key = term.inkey(timeout=0.1)
        if key:
            return self.keyboard_handler.handle_key(ui_state, key)
        return ui_state, None
```

#### 4.2 Simplified Event Loop

**Solution**: Clean main loop using systems

```python
# ui/app.py (simplified)
def main_loop(term: Terminal, ctx: AppContext) -> AppContext:
    # Initialize systems
    render_system = RenderSystem()
    polling_system = PollingSystem()
    input_system = InputSystem(KeyboardHandler())
    
    # Initial state
    ui_state = create_initial_state()
    
    try:
        while not should_quit:
            # Update systems
            ctx, ui_state = polling_system.update(ctx, ui_state)
            ui_state, command = input_system.handle_input(term, ui_state)
            
            # Execute command if any
            if command:
                ctx, ui_state, should_quit = execute_command(ctx, ui_state, command)
            
            # Render
            render_system.render(ctx, ui_state)
            
    except KeyboardInterrupt:
        # Cleanup
        pass
    
    return ctx
```

### Phase 5: Command Handling Improvements (Medium Impact, Low Risk)

#### 5.1 Generic Command Handler System

**Problem**: Command executor becoming complex with many internal command types

**Solution**: Generic handler system with base classes

```python
# ui/commands/base.py
class CommandHandler:
    def __init__(self, action: str):
        self.action = action
        
    @abstractmethod
    def execute(self, ctx: AppContext, ui_state: UIState, data: dict) -> tuple[AppContext, UIState]:
        pass

class DatabaseRefreshMixin:
    def refresh_ui_state(self, ui_state: UIState, ctx: AppContext) -> UIState:
        # Common refresh logic used by multiple handlers
        pass

# ui/commands/playlist_handlers.py
class CreatePlaylistHandler(CommandHandler, DatabaseRefreshMixin):
    def execute(self, ctx: AppContext, ui_state: UIState, data: dict) -> tuple[AppContext, UIState]:
        # Specific implementation
        refreshed_state = self.refresh_ui_state(ui_state, ctx)
        return ctx, refreshed_state
```

## Implementation Plan

### Phase 1: Common Patterns (Week 1-2)
1. **Extract ScrollableList component**
   - Create `ui/components/scrollable_list.py`
   - Refactor `track_viewer.py` to use ScrollableList
   - Refactor `palette.py` to use ScrollableList
   - Refactor `analytics_viewer.py` to use ScrollableList

2. **Create Modal system**
   - Create `ui/components/modal.py`
   - Extract common modal rendering patterns
   - Update all modal components to use common system

3. **Extract navigation mixins**
   - Create `ui/mixins/navigation.py`
   - Extract common navigation patterns
   - Update handlers to use mixins

### Phase 2: State Management (Week 3-4)
1. **Create modular state structure**
   - Create `ui/state/` directory structure
   - Split `state.py` into focused modules
   - Update imports across codebase

2. **Simplify state update functions**
   - Create `ui/state/updaters.py`
   - Replace repetitive helper functions
   - Update all state mutation code

### Phase 3: Keyboard Handling (Week 5-6)
1. **Create mode-based handlers**
   - Create `ui/handlers/` directory structure
   - Implement base classes and mixins
   - Split `keyboard.py` into mode-specific handlers

2. **Refactor keyboard handling**
   - Update `keyboard.py` to use new system
   - Test all keyboard interactions
   - Fix any regressions

### Phase 4: Event Loop (Week 7-8)
1. **Extract systems**
   - Create `ui/systems/` directory
   - Implement RenderSystem, PollingSystem, InputSystem
   - Test systems independently

2. **Refactor main loop**
   - Simplify `app.py` main_loop function
   - Integrate systems
   - Test full UI functionality

### Phase 5: Command Handling (Week 9)
1. **Create generic command system**
   - Create `ui/commands/` directory
   - Implement base classes and mixins
   - Refactor existing command handlers

2. **Final integration and testing**
   - Complete integration testing
   - Performance testing
   - Documentation updates

## Expected Benefits

### Complexity Reduction
- **Before**: 9,833 lines across UI components
- **After**: ~6,000 lines (39% reduction)
- **State management**: 1,500 → 800 lines (47% reduction)
- **Keyboard handling**: 1,486 → 600 lines (60% reduction)
- **Event loop**: 1,172 → 400 lines (66% reduction)

### Maintainability Improvements
- **Clear separation of concerns** through modular architecture
- **Reduced code duplication** via common abstractions
- **Easier testing** through focused, single-responsibility components
- **Better extensibility** through plugin-like handler system

### Performance Benefits
- **Reduced memory usage** through more efficient state management
- **Faster rendering** through optimized dirty region tracking
- **Smoother interactions** through focused input handling

## Risk Assessment

### Low Risk Changes
- Extracting common patterns (ScrollableList, Modal)
- Creating navigation mixins
- Generic command handler base classes

### Medium Risk Changes  
- Splitting state management (requires careful migration)
- Mode-based keyboard handling (complex interaction testing)

### High Risk Changes
- Event loop refactoring (core functionality)
- Major architectural changes

### Mitigation Strategies
1. **Incremental migration** - change one component at a time
2. **Comprehensive testing** - test each phase thoroughly
3. **Backward compatibility** - maintain old interfaces during transition
4. **Feature flags** - ability to switch between old/new implementations

## Success Metrics

1. **Code complexity reduction**: 40% fewer lines of code
2. **Maintainability**: Faster bug fixes and feature additions
3. **Testability**: Higher test coverage with simpler tests
4. **Performance**: No regression in UI responsiveness
5. **Developer experience**: Easier onboarding for new contributors

## Conclusion

This optimization plan will significantly reduce UI complexity while maintaining all functionality. The phased approach allows for incremental improvements with minimal risk. The result will be a more maintainable, testable, and extensible UI architecture that can better support future growth.