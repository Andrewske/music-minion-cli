---
task: 01-create-sidebar-components
status: pending
depends: [00-create-filter-store]
files:
  - path: web/frontend/src/components/sidebar/Sidebar.tsx
    action: create
  - path: web/frontend/src/components/sidebar/SidebarNav.tsx
    action: create
  - path: web/frontend/src/components/sidebar/SidebarToggle.tsx
    action: create
  - path: web/frontend/src/components/sidebar/SidebarSection.tsx
    action: create
---

# Create Core Sidebar Components

## Context
Build the foundational sidebar components that will replace the header navigation. This is the core UI infrastructure that all other tasks depend on.

## Files to Modify/Create
- `web/frontend/src/components/sidebar/Sidebar.tsx` (new)
- `web/frontend/src/components/sidebar/SidebarNav.tsx` (new)
- `web/frontend/src/components/sidebar/SidebarToggle.tsx` (new)
- `web/frontend/src/components/sidebar/SidebarSection.tsx` (new)

## Implementation Details

### Sidebar.tsx - Main Container
```typescript
// State management
const [isExpanded, setIsExpanded] = useState(() => {
  const stored = localStorage.getItem('music-minion-sidebar-expanded')
  return stored !== null ? JSON.parse(stored) : true
})

// Persist to localStorage
useEffect(() => {
  localStorage.setItem('music-minion-sidebar-expanded', JSON.stringify(isExpanded))
}, [isExpanded])
```

**Styling:**
- Width: `w-[72px]` collapsed, `w-[280px]` expanded
- Background: `bg-black`
- Border: `border-r border-obsidian-border`
- Transition: `transition-all duration-300 ease-in-out`
- Height: `h-[calc(100vh-64px)]` (accounts for 64px PlayerBar at bottom)

**Structure:**
```
<aside>
  <SidebarHeader with logo + toggle>
  <SidebarNav />
  <Divider />
  <SidebarSection> {/* Route-aware context */}
    {children}
  </SidebarSection>
</aside>
```

### SidebarNav.tsx - Navigation Items
6 nav items with tooltips:
- Home (House icon) → "/"
- History (Clock icon) → "/history"
- Comparison (Trophy icon) → "/comparison"
- Playlist Builder (ListMusic icon) → "/playlist-builder"
- YouTube (Youtube icon) → "/youtube"
- Emoji Settings (Smile icon) → "/emoji-settings"

**Tooltip implementation (collapsed state):**
```tsx
<div className="group relative">
  <Link to={href} aria-label={label} ...>
    <Icon />
    {isExpanded && <span>{label}</span>}
  </Link>
  {!isExpanded && (
    <div className="absolute left-full ml-2 hidden group-hover:block
                    bg-obsidian-surface border border-obsidian-border
                    text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50"
         role="tooltip">
      {label}
    </div>
  )}
</div>
```

Note: `aria-label` ensures screen readers announce the nav item even when collapsed.

**Active state styling:**
- `bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent`
- Icon: `text-obsidian-accent`

### SidebarToggle.tsx
Simple chevron button:
- `ChevronLeft` when expanded → collapse
- `ChevronRight` when collapsed → expand

### SidebarSection.tsx
Collapsible wrapper for sidebar content sections:
```tsx
interface SidebarSectionProps {
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  sidebarExpanded: boolean; // parent sidebar state
}

export function SidebarSection({ title, children, defaultExpanded = true, sidebarExpanded }: SidebarSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Hide entire section when sidebar is collapsed
  if (!sidebarExpanded) return null;

  return (
    <div className="border-t border-obsidian-border">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-white/60 hover:text-white"
      >
        <span className="text-xs tracking-[0.2em] uppercase">{title}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isExpanded ? '' : '-rotate-90'}`} />
      </button>
      {isExpanded && (
        <div className="px-2 pb-2 overflow-y-auto max-h-[30vh]">
          {children}
        </div>
      )}
    </div>
  );
}
```

Features:
- Collapsible via chevron button
- Hidden when parent sidebar is collapsed (icons-only mode)
- Scrollable content area with max height
- Persists expand/collapse state locally (could add localStorage if needed)

## Verification
1. `npm run dev` and verify sidebar renders
2. Click toggle - sidebar collapses/expands with animation
3. Hover collapsed nav items - tooltips appear
4. Navigate between routes - active state updates
5. Refresh page - collapse state persists
