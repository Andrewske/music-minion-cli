---
task: 04-restyle-filter-panel
status: pending
depends:
  - 03-unify-playlist-builder
files:
  - path: web/frontend/src/components/builder/FilterPanel.tsx
    action: modify
  - path: web/frontend/src/components/builder/FilterEditor.tsx
    action: modify
  - path: web/frontend/src/components/builder/FilterItem.tsx
    action: modify
  - path: web/frontend/src/components/builder/ConjunctionToggle.tsx
    action: modify
---

# Restyle FilterPanel to Obsidian Theme

## Context
FilterPanel and related components use slate/purple theme which doesn't match the obsidian theme of the manual playlist builder. Update styling for visual consistency.

## Files to Modify/Create
- `web/frontend/src/components/builder/FilterPanel.tsx` (modify)
- `web/frontend/src/components/builder/FilterEditor.tsx` (modify)
- `web/frontend/src/components/builder/FilterItem.tsx` (modify)
- `web/frontend/src/components/builder/ConjunctionToggle.tsx` (modify)

## Implementation Details

### Color Replacements
| Current | Replace With |
|---------|--------------|
| `bg-slate-900` | `bg-black` |
| `bg-slate-800` | `bg-white/5` |
| `bg-slate-700` | `bg-white/10` |
| `text-purple-400` | `text-obsidian-accent` |
| `text-purple-600` | `text-obsidian-accent` |
| `bg-purple-600` | `bg-obsidian-accent` |
| `hover:bg-purple-700` | `hover:bg-obsidian-accent/80` |
| `border-purple-*` | `border-obsidian-accent` |
| `text-slate-400` | `text-white/40` |
| `text-slate-300` | `text-white/60` |
| `text-gray-400` | `text-white/40` |
| `rounded-lg` | (remove or use minimal rounding) |
| `rounded-full` on pills | `border border-obsidian-border` |

### FilterPanel.tsx Specifics
- Remove excess padding (p-4 → p-2 or none)
- Make header text smaller
- Use border-obsidian-border for section dividers

### FilterEditor.tsx Specifics
- Style dropdown/select inputs with obsidian theme
- Style text inputs with obsidian borders
- Emoji picker should match theme if possible

### FilterItem.tsx Specifics
- Use subtle borders instead of colored backgrounds
- Hover state: `hover:bg-white/5`

### ConjunctionToggle.tsx Specifics
- AND/OR toggle should use obsidian-accent for active state
- Inactive state: `text-white/40`

## Verification
1. All filter components render with obsidian theme
2. No slate/purple colors remain visible
3. UI remains readable and interactive
4. Hover/focus states work correctly
5. Visual consistency with rest of builder
