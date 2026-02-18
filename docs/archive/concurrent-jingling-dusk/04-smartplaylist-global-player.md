---
task: 04-smartplaylist-global-player
status: done
depends: [02-integrate-useplayer, 03-wavesurfer-external-audio]
files:
  - path: web/frontend/src/pages/PlaylistBuilder.tsx
    action: modify
---

# SmartPlaylistEditor Global Player Integration

## Context
SmartPlaylistEditor currently maintains local playback state separate from the global player. This task removes the local state and wires all playback through the global playerStore.

## Files to Modify/Create
- web/frontend/src/pages/SmartPlaylistEditor.tsx (modify)

## Implementation Details

### 1. Remove local playback state

**DELETE these state declarations:**
```typescript
const [isPlaying, setIsPlaying] = useState(false);
const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
```

### 2. Import and use global player

**ADD import:**
```typescript
import { usePlayerStore } from '../stores/playerStore';
```

**ADD store usage:**
```typescript
const { currentTrack, isPlaying, play, pause, resume } = usePlayerStore();
```

### 3. Update track click handler

**REPLACE local selection with global play:**
```typescript
const handleTrackClick = (track: Track) => {
  play(track, { type: 'builder', playlist_id: playlistId });
};
```

### 4. Update play/pause toggle

**REPLACE local toggle:**
```typescript
const handleTogglePlayPause = () => {
  if (isPlaying) {
    pause();
  } else {
    resume();
  }
};
```

### 5. Update WaveformPlayer props

**CHANGE track source:**
```typescript
<WaveformPlayer
  track={currentTrack}  // Was: selectedTrack
  isPlaying={isPlaying}  // Now from global store
  onTogglePlayPause={handleTogglePlayPause}
  onFinish={() => pause()}  // Don't auto-advance in builder
/>
```

### 6. Update review mode

Review mode's `currentTrack` from `useSmartPlaylistEditor` hook should also trigger global player:

```typescript
// In review mode, when currentTrackId changes, play it
useEffect(() => {
  if (isReviewMode && currentTrack) {
    play(currentTrack, { type: 'builder', playlist_id: playlistId });
  }
}, [isReviewMode, currentTrack?.id]);
```

## Verification
- Click track in builder → plays via global PlayerBar
- PlayerBar shows correct track info
- Waveform in builder shows progress
- Seeking in builder waveform seeks global player
- Review mode track changes update global player
