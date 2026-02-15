# Playlist Builder Emoji Picker Design

**Date:** 2026-02-14
**Status:** Approved

## Overview

Add emoji tagging to the playlist builder's main track display, allowing users to tag tracks with emojis while reviewing candidates. The implementation will reuse existing emoji infrastructure (`useTrackEmojis` hook, `EmojiPicker` modal) with custom Obsidian-styled UI.

## Requirements

- Users can add/remove emojis from the current track being reviewed
- Emoji UI appears inline with metadata pills (BPM, key, genre, year)
- Styling matches Obsidian builder aesthetic (black bg, amber accent, SF Mono)
- Reuses existing API logic and picker modal

## Component Architecture

**New Component:**
- `ObsidianEmojiActions` - builder-specific emoji UI (inline in `ObsidianMinimalBuilder.tsx`)

**Reused Components/Hooks:**
- `useTrackEmojis(track, onUpdate)` - existing hook for add/remove logic, API calls, optimistic updates
- `EmojiPicker` - existing modal picker (already dark-themed)

**Integration Point:**
- Main track display section, after metadata pills (line ~210-223 in `ObsidianMinimalBuilder.tsx`)

## Visual Design

**Obsidian Aesthetic:**
- Background: Pure black (`bg-black`)
- Accent: Amber (`text-obsidian-accent` on hover)
- Font: SF Mono (`font-sf-mono`) matching metadata pills
- Borders: Hairline (`border-white/20` or `border-obsidian-border`)

**Layout:**
```
[128 BPM] [Cm] [House] [2023] [🔥] [💎] [+ Emoji]
                                ↑ emojis    ↑ add button
```

**Emoji Display:**
- Small size (16-20px)
- Horizontal list with gaps
- Hover: Show × to remove, amber accent
- Click × to remove emoji

**Add Button:**
- Text: `+ Emoji`
- Style: `text-white/40` default, `text-obsidian-accent` on hover
- Click: Opens `EmojiPicker` modal
- Disabled state when API call in progress

## Data Flow

**Track Data:**
- `currentTrack` already includes `emojis?: string[]` from backend
- Backend already returns emojis in candidates response
- Component receives track from either `nowPlayingTrack` or `candidates[queueIndex]`

**State Management:**
- Local: `showPicker` boolean for modal visibility
- `useTrackEmojis(currentTrack, handleUpdate)` manages all API logic
- Optimistic updates handled by hook (instant UI feedback)
- Query invalidation handled by hook (fresh data on refetch)

**Update Handler:**
- When emoji changes, query refetches automatically
- Optimistic updates provide instant feedback
- UI stays in sync with server state

## Implementation Details

**Component Props:**
```typescript
interface ObsidianEmojiActionsProps {
  track: Track;
  onUpdate: (updatedTrack: Track) => void;
}
```

**Component Structure:**
1. `useState(showPicker)` for modal toggle
2. `useTrackEmojis(track, onUpdate)` for add/remove logic
3. Render emoji list (each clickable with × on hover)
4. Render `+ Emoji` button
5. Conditionally render `EmojiPicker` modal

**Styling Classes:**
- Container: `flex gap-4 mt-6` (matching metadata pills container)
- Emoji wrapper: `flex items-center gap-2`
- Individual emoji: `relative group cursor-pointer` with hover × overlay
- Add button: `text-xs font-sf-mono text-white/40 hover:text-obsidian-accent transition-colors cursor-pointer`

## Success Criteria

- [x] Design approved
- [ ] Component renders inline with metadata
- [ ] Emojis display correctly with current track data
- [ ] Add emoji opens picker modal
- [ ] Remove emoji works on click
- [ ] Styling matches Obsidian aesthetic
- [ ] Optimistic updates work correctly
- [ ] No regressions in other emoji features
