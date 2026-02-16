# PlaylistBuilder + Obsidian Design Merge

## Summary

Merge `ObsidianMinimalBuilder.tsx` design into `PlaylistBuilder.tsx` and restyle universal components to use the Obsidian design system (pure black background, amber accent, hairline borders).

## Context

- Two playlist builder implementations exist: `PlaylistBuilder` (functional) and `ObsidianMinimalBuilder` (better design)
- Filters moved to global sidebar, removing need for FilterPanel in builder
- Obsidian design is the site-wide standard

## Changes

### PlaylistBuilder.tsx

**Keep:**
- Props interface: `{ playlistId, playlistName, playlistType }`
- Smart playlist routing to `SmartPlaylistEditor`
- All hooks: `useBuilderSession`, `useIPCWebSocket`, `useInfiniteQuery`

**Remove:**
- `FilterPanel` import and grid layout
- `TrackDisplay` inline component
- `StatsPanel` component
- Console.log statements

**Adopt from ObsidianBuilderMain:**
- Pure black background (`bg-black`)
- Single-column layout (`max-w-6xl mx-auto`)
- Sticky player section on mobile
- Minimal button styling (border-only)
- Amber accent color scheme

### WaveformPlayer.tsx

Restyle to obsidian:
- Play button: `text-obsidian-accent` icon only (remove emerald rounded button)
- Time display: `text-white/30 font-sf-mono`
- Keep Media Session API for phone notifications
- Keep error handling, restyle colors

### TrackQueueTable.tsx

Restyle to obsidian:
- Borders: `border-obsidian-border`
- Headers: `text-white/30 hover:text-white/60`
- Playing row: `bg-obsidian-accent/10 border-l-obsidian-accent`
- Keep TanStack virtualization
- Add mobile card view (use existing `TrackQueueCard`)

### EmojiReactions.tsx

Restyle to obsidian:
- Remove slate-800 backgrounds
- Hover: `hover:opacity-70` with × indicator
- Remove debug overlay code (lines 54-60)

### EmojiTrackActions.tsx

- Remove console.log debug statements

## File Cleanup

**Delete:**
- `web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx`

## Design Tokens

```
bg-black           - Main background
obsidian-accent    - Amber accent (buttons, highlights)
obsidian-border    - Hairline borders
white/30-60        - Secondary text
font-sf-mono       - Monospace elements (time, BPM)
font-inter         - Body text
```
