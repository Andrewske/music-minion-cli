---
task: 03-wavesurfer-external-audio
status: pending
depends: [01-shared-audio-context]
files:
  - path: web/frontend/src/hooks/useWavesurfer.ts
    action: modify
  - path: web/frontend/src/components/WaveformPlayer.tsx
    action: modify
---

# WaveSurfer External Audio Support

## Context
WaveSurfer currently creates its own MediaElement for audio playback. This task adds support for using an external audio element, enabling visualization without dual playback.

## Files to Modify/Create
- web/frontend/src/hooks/useWavesurfer.ts (modify)
- web/frontend/src/components/WaveformPlayer.tsx (modify)

## Implementation Details

### 1. Modify useWavesurfer.ts

**Add externalAudio option to interface:**
```typescript
interface UseWavesurferOptions {
  trackId: number;
  isPlaying: boolean;
  onFinish?: () => void;
  onReady?: (duration: number) => void;
  onSeek?: (progress: number) => void;
  onTimeUpdate?: (currentTime: number) => void;
  externalAudio?: HTMLAudioElement | null;  // NEW
}
```

**Modify createWavesurferConfig:**
```typescript
function createWavesurferConfig(
  container: HTMLDivElement,
  externalAudio?: HTMLAudioElement | null,
  peaks?: number[],
  duration?: number
) {
  const baseConfig = {
    container,
    waveColor: '#475569',
    progressColor: '#10b981',
    cursorColor: '#10b981',
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    height: 64,
    normalize: true,
  };

  // External audio: pass media + peaks + duration in config (no load() needed)
  if (externalAudio && peaks && duration) {
    return { ...baseConfig, media: externalAudio, peaks: [peaks], duration };
  }
  return baseConfig;
}
```

**In initWavesurfer, conditionally load audio:**
```typescript
const wavesurfer = WaveSurfer.create(
  createWavesurferConfig(
    containerRef.current,
    externalAudio,
    waveformData?.peaks,
    trackDuration  // Pass track duration from props/store
  )
);

// Only call load() for internal audio mode (no external element)
if (!externalAudio) {
  const streamUrl = getStreamUrl(trackId);
  if (waveformData?.peaks) {
    wavesurfer.load(streamUrl, [waveformData.peaks]);
  } else {
    wavesurfer.load(streamUrl);
  }
}
// External audio mode: WaveSurfer auto-initializes from config, no load() needed
```

### 2. Modify WaveformPlayer.tsx

**Import context and store:**
```typescript
import { useAudioElement } from '../contexts/AudioElementContext';
import { usePlayerStore } from '../stores/playerStore';
```

**Determine if this waveform controls the global track:**
```typescript
const sharedAudio = useAudioElement();
const globalTrackId = usePlayerStore(state => state.currentTrack?.id);

// Only use shared audio if this track is the global current track
const audioElement = track.id === globalTrackId ? sharedAudio : null;

const { containerRef, currentTime, duration, error, retryLoad } = useWavesurfer({
  trackId: track.id,
  isPlaying,
  onFinish,
  externalAudio: audioElement,  // Pass shared audio when applicable
  onSeek: audioElement ? handleSeekViaStore : undefined,  // Route through store when external
});
```

**Route seeks through playerStore (avoids dual control conflicts):**
```typescript
const { seek } = usePlayerStore();

// When using external audio, route waveform seeks through the store
// This ensures WebSocket sync to other devices
const handleSeekViaStore = useCallback((progress: number) => {
  if (!track.duration) return;
  const positionMs = progress * track.duration * 1000;
  seek(positionMs);
}, [seek, track.duration]);
```

## Verification
- Waveform still renders correctly
- Seeking on waveform seeks the audio
- Time updates correctly during playback
- Finish callback fires when track ends
- Waveform seek syncs to other devices via WebSocket (routes through playerStore.seek)
