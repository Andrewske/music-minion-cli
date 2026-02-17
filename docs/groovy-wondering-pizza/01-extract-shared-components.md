---
task: 01-extract-shared-components
status: pending
depends: []
files:
  - path: web/frontend/src/components/builder/TrackDisplay.tsx
    action: create
  - path: web/frontend/src/components/builder/WaveformSection.tsx
    action: create
  - path: web/frontend/src/components/builder/BuilderActions.tsx
    action: create
---

# Extract Shared Components

## Context
The smart playlist builder and manual playlist builder share UI patterns but currently duplicate code. Extract common components to enable code reuse and visual consistency.

## Files to Modify/Create
- `web/frontend/src/components/builder/TrackDisplay.tsx` (new)
- `web/frontend/src/components/builder/WaveformSection.tsx` (new)
- `web/frontend/src/components/builder/BuilderActions.tsx` (new)

## Implementation Details

### TrackDisplay.tsx
Extract from PlaylistBuilder.tsx lines 215-242:
- Artist (obsidian-accent color)
- Title (large white text)
- Album (muted)
- Metadata pills (BPM, key, genre, year)
- EmojiTrackActions component

```typescript
interface TrackDisplayProps {
  track: Track;
  onEmojiUpdate?: (track: { id: number; emojis?: string[] }) => void;
}
```

### WaveformSection.tsx
Extract from PlaylistBuilder.tsx lines 244-281:
- WaveformPlayer wrapper with consistent height (h-16)
- Loop toggle checkbox below waveform

```typescript
interface WaveformSectionProps {
  track: Track;
  isPlaying: boolean;
  loopEnabled: boolean;
  onTogglePlayPause: () => void;
  onLoopChange: (enabled: boolean) => void;
  onFinish: () => void;
}
```

### BuilderActions.tsx
Type-aware action buttons:
- Manual: "Add" (primary, obsidian-accent border) + "Skip" (secondary, white/20 border)
- Smart: "Skip" only (secondary style)

```typescript
interface BuilderActionsProps {
  playlistType: 'manual' | 'smart';
  onAdd?: () => void;
  onSkip: () => void;
  isAddingTrack?: boolean;
  isSkippingTrack: boolean;
}
```

## Verification
1. Components compile without TypeScript errors
2. Each component can be imported and rendered in isolation
3. Prop interfaces are correctly typed
