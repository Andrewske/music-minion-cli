---
task: 04-sidebar-component
status: done
depends: [03-frontend-state]
files:
  - path: web/frontend/src/components/sidebar/SidebarQuickTag.tsx
    action: create
  - path: web/frontend/src/routes/__root.tsx
    action: modify
---

# Sidebar Component - Quick Tag UI

## Context
The visible voting interface. Displays current dimension with emoji buttons, navigation arrows, and progress dots. Integrates with playerStore for current track and quickTagStore for voting logic.

## Files to Modify/Create
- web/frontend/src/components/sidebar/SidebarQuickTag.tsx (create)
- web/frontend/src/routes/__root.tsx (modify)

## Implementation Details

### 1. Create Component (`SidebarQuickTag.tsx`)

**Props:**
```typescript
interface SidebarQuickTagProps {
  sidebarExpanded: boolean;  // Injected by Sidebar.tsx
}
```

**Wrapper:** Use `SidebarSection` for consistent collapse behavior:
```tsx
<SidebarSection title="Quick Tag" sidebarExpanded={sidebarExpanded}>
  {/* vote UI content */}
</SidebarSection>
```

**Content Structure (inside SidebarSection):**
```
┌──────────────────────────┐
│      ◄  1/10  ►          │  ← ChevronLeft/Right buttons + count
│   Pristine vs Filthy     │  ← currentDimension.label
│                          │
│     ✨    ─    💀        │  ← emoji buttons + Minus icon for skip
│                          │
│    ●○○○○○○○○○            │  ← progress dots
└──────────────────────────┘
```

**Key Elements:**

1. **Dimension Navigation:**
   - ChevronLeft/ChevronRight icons from lucide-react
   - Display `{currentDimensionIndex + 1}/{dimensions.length}`
   - Click arrows to call `prevDimension()` / `nextDimension()`

2. **Label Display:**
   - `currentDimension.label` (e.g., "Pristine vs Filthy")
   - Smaller text, centered

3. **Vote Buttons:**
   - Left emoji: `onClick={() => handleVote(-1)}`
   - Skip (Minus icon): `onClick={() => handleVote(0)}`
   - Right emoji: `onClick={() => handleVote(1)}`
   - Hover: `hover:scale-125 transition-transform`

4. **Progress Dots:**
   - Map over dimensions, render dot for each
   - Current index highlighted with `bg-obsidian-accent`
   - Others: `bg-white/20`

5. **Empty State:**
   - If no `currentTrack`: Show "Play a track to start tagging"
   - If no dimensions loaded: Show loading or trigger `loadDimensions()`

**Hooks & Initialization:**
```typescript
const { currentTrack } = usePlayerStore();
const {
  dimensions,
  currentDimensionIndex,
  isLoading,
  error,
  loadDimensions,
  vote,
  nextDimension,
  prevDimension
} = useQuickTagStore();

// Derive currentDimension via selector
const currentDimension = useQuickTagStore(
  s => s.dimensions[s.currentDimensionIndex] ?? null
);

// Initialize dimensions on mount
useEffect(() => {
  if (dimensions.length === 0 && !isLoading) {
    loadDimensions();
  }
}, [dimensions.length, isLoading, loadDimensions]);
```

### 2. Integrate in Root Layout (`__root.tsx`)

Add import:
```typescript
import { SidebarQuickTag } from '../components/sidebar/SidebarQuickTag'
```

Add as first child of Sidebar (props are injected automatically by Sidebar.tsx):
```tsx
<Sidebar>
  <SidebarQuickTag />
  <SidebarPlaylists />
  <SidebarFilters />
</Sidebar>
```

## Verification
1. Start app: `music-minion --web`
2. Open browser to http://localhost:5173
3. Verify Quick Tag section appears at top of sidebar
4. Play a track
5. Click an emoji → should see network request to `/api/quicktag/vote`
6. Verify dimension advances after voting
7. Click nav arrows → dimension should change
8. Progress dots should update to show current position
9. Change track → dimension should stay the same
10. Vote on new track → should work without issues
