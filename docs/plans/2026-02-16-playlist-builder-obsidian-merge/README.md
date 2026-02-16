# PlaylistBuilder Obsidian Merge

## Overview
Merge ObsidianMinimalBuilder design into PlaylistBuilder and restyle universal components (WaveformPlayer, TrackQueueTable, EmojiReactions) to obsidian black/amber theme. Replace slate-colored grid layout with single-column obsidian design. Add mobile card view to TrackQueueTable.

## Task Sequence

1. [01-clean-up-emoji-debug.md](./01-clean-up-emoji-debug.md) - Remove debug overlays and console.logs from emoji components
2. [02-restyle-emoji-reactions.md](./02-restyle-emoji-reactions.md) - Convert EmojiReactions to obsidian theme with hover × indicator
3. [03-restyle-waveform-player.md](./03-restyle-waveform-player.md) - Convert WaveformPlayer to obsidian theme
4. [04-restyle-track-queue-table.md](./04-restyle-track-queue-table.md) - Convert TrackQueueTable to obsidian theme
5. [05-add-mobile-card-view.md](./05-add-mobile-card-view.md) - Add responsive mobile card view with sort selector
6. [06-rewrite-playlist-builder.md](./06-rewrite-playlist-builder.md) - Main integration: replace layout with obsidian design
7. [07-cleanup-and-verify.md](./07-cleanup-and-verify.md) - Delete ObsidianMinimalBuilder and final verification

## Dependency Graph

```
01-clean-up-emoji-debug ──► 02-restyle-emoji-reactions ─┐
                                                        │
03-restyle-waveform-player ─────────────────────────────┼──► 06-rewrite-playlist-builder ──► 07-cleanup-and-verify
                                                        │
04-restyle-track-queue-table ──► 05-add-mobile-card-view┘
```

**Batch 1 (parallel):** 01, 03, 04
**Batch 2 (parallel):** 02, 05
**Batch 3:** 06
**Batch 4:** 07

## Success Criteria
- Build succeeds: `cd web/frontend && npm run build`
- Playlist builder displays with black background, amber accents
- Single-column layout on all screen sizes
- Waveform player works with obsidian styling
- Track queue table has obsidian styling with working sort
- Mobile card view works with sort selector
- Emoji reactions have hover × indicator
- ObsidianMinimalBuilder.tsx is deleted

## Dependencies
- React, TailwindCSS, TanStack Table/Virtual, WaveSurfer.js
- Existing obsidian theme CSS variables (obsidian-accent, obsidian-border)
- TrackQueueCard component for mobile view
