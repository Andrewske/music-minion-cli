# Create EmojiReactions Component

## Files to Create
- `web/frontend/src/components/EmojiReactions.tsx` (new)

## Implementation Details

### Component Purpose
Display emoji badges with click-to-remove functionality. Shows current track's emojis and provides "+ Add" button. This is a **presentational component** - parent handles all logic via callbacks.

### Component Interface

```tsx
interface EmojiReactionsProps {
  trackId: number;
  emojis: string[];
  onRemove: (emoji: string) => void;
  onAddClick: () => void;
  compact?: boolean;  // For tables/mini-displays - smaller badges, no "+ Add" button
  className?: string; // Allow parent to control layout
  isAdding?: boolean;  // NEW: Disable "+ Add" while adding
  isRemoving?: boolean;  // NEW: Visual feedback while removing
}

export function EmojiReactions({
  trackId,
  emojis,
  onRemove,
  onAddClick,
  compact = false,
  className = '',
  isAdding = false,
  isRemoving = false
}: EmojiReactionsProps): JSX.Element {
  // Implementation
}
```

### UI Structure

```tsx
<div className={`flex flex-wrap gap-2 items-center ${className}`}>
  {/* Emoji badges */}
  {emojis.map((emoji) => (
    <button
      key={emoji}
      onClick={() => onRemove(emoji)}
      className={`
        ${compact ? 'px-1.5 py-0.5 text-base' : 'px-2 py-1 text-lg'}
        bg-slate-800 hover:bg-red-600 rounded-md transition-colors
      `}
      aria-label={`Remove ${emoji}`}
    >
      {emoji}
    </button>
  ))}

  {/* Add button (hidden in compact mode) */}
  {!compact && (
    <button
      onClick={onAddClick}
      disabled={isAdding}
      className={`px-3 py-1 rounded-md text-sm font-medium text-white transition-colors ${
        isAdding
          ? 'bg-emerald-700 opacity-50 cursor-not-allowed'
          : 'bg-emerald-600 hover:bg-emerald-500'
      }`}
      aria-label="Add emoji"
    >
      {isAdding ? 'Adding...' : '+ Add'}
    </button>
  )}
</div>
```

### Styling Guidelines
- **Emoji badges:**
  - Default: `bg-slate-800` (dark gray)
  - Hover: `bg-red-600` (red to indicate removal)
  - Size: `text-lg` for emoji visibility
  - Clickable with cursor pointer (implicit from button)

- **Add button:**
  - Color: `bg-emerald-600` (emerald green)
  - Hover: `bg-emerald-500` (lighter emerald)
  - Text: `text-sm font-medium text-white`

### Behavior
- Click emoji badge → calls `onRemove(emoji)` → parent handles API call + state update
- Click "+ Add" → calls `onAddClick()` → parent opens emoji picker
- Emojis wrap to multiple rows if needed (`flex-wrap`)

## Acceptance Criteria
- [ ] Component compiles without TypeScript errors
- [ ] Component renders with empty emojis array (shows only "+ Add" button)
- [ ] Component renders with multiple emojis (all badges visible)
- [ ] Clicking emoji badge calls `onRemove` with correct emoji
- [ ] Clicking "+ Add" button calls `onAddClick`
- [ ] Hover states work (badges turn red, add button lightens)
- [ ] Accessibility: aria-labels present on all buttons

## Dependencies
None - this is a standalone presentational component
