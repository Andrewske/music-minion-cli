---
task: 01-shared-audio-context
status: pending
depends: []
files:
  - path: web/frontend/src/contexts/AudioElementContext.tsx
    action: create
  - path: web/frontend/src/routes/__root.tsx
    action: modify
---

# Create Shared Audio Element Context

## Context
The root cause of dual playback is multiple Audio elements. This task creates a single shared Audio element via React Context that all components will use.

## Files to Modify/Create
- web/frontend/src/contexts/AudioElementContext.tsx (new)
- web/frontend/src/routes/__root.tsx (modify)

## Implementation Details

### 1. Create AudioElementContext.tsx

```typescript
import { createContext, useContext, useRef, type RefObject, type ReactNode } from 'react';

const AudioElementContext = createContext<RefObject<HTMLAudioElement> | null>(null);

export function AudioElementProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  return (
    <AudioElementContext.Provider value={audioRef}>
      <audio ref={audioRef} preload="auto" style={{ display: 'none' }} />
      {children}
    </AudioElementContext.Provider>
  );
}

export function useAudioElement(): HTMLAudioElement | null {
  const ref = useContext(AudioElementContext);
  if (!ref) {
    throw new Error('useAudioElement must be used within AudioElementProvider');
  }
  return ref.current;
}
```

### 2. Update __root.tsx

Wrap the app content in `<AudioElementProvider>`:

```typescript
import { AudioElementProvider } from '../contexts/AudioElementContext';

// In RootComponent, wrap children:
<AudioElementProvider>
  {/* existing layout */}
</AudioElementProvider>
```

## Verification
- App starts without errors
- Hidden audio element exists in DOM (inspect with dev tools)
- No functional changes yet - existing playback still works
