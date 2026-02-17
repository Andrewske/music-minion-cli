---
task: 02-integrate-useplayer
status: pending
depends: [01-shared-audio-context]
files:
  - path: web/frontend/src/hooks/usePlayer.ts
    action: modify
---

# Integrate usePlayer with Shared Audio

## Context
The global player hook currently creates its own Audio element. This task switches it to use the shared context audio, making it the single source of playback.

## Files to Modify/Create
- web/frontend/src/hooks/usePlayer.ts (modify)

## Implementation Details

### Changes to usePlayer.ts

1. **Import the context hook:**
```typescript
import { useAudioElement } from '../contexts/AudioElementContext';
```

2. **Replace audioRef creation** (lines 6, 14-20):
```typescript
// BEFORE
const audioRef = useRef<HTMLAudioElement | null>(null);
useEffect(() => {
  if (!audioRef.current) {
    audioRef.current = new Audio();
    // ...
  }
}, []);

// AFTER
const audio = useAudioElement();
```

3. **Update all audioRef.current references** to just `audio`:
- Line 34: `if (audioRef.current)` → `if (audio)`
- Line 35: `audioRef.current.volume` → `audio.volume`
- Line 40: `audioRef.current.muted` → `audio.muted`
- And so on for all ~15 references

4. **Remove the cleanup effect** (lines 23-29) - context manages lifecycle now

5. **Add early return if no audio:**
```typescript
const audio = useAudioElement();
if (!audio) return store; // Context not ready yet
```

## Verification
- Global PlayerBar play/pause still works
- Volume/mute controls work
- Track advancement on ended works
- Seek position syncs correctly
