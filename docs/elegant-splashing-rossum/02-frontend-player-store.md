---
task: 02-frontend-player-store
status: done
depends: [01-backend-player-api]
files:
  - path: web/frontend/src/stores/playerStore.ts
    action: create
  - path: web/frontend/src/hooks/usePlayer.ts
    action: create
  - path: web/frontend/src/hooks/useSyncWebSocket.ts
    action: modify
---

# Frontend Player Store

## Context
Creates the Zustand store and hook that manage all playback state on the frontend. Handles device registration, WebSocket sync, position tracking, and audio element management. Only the active device actually plays audio.

## Files to Modify/Create
- `web/frontend/src/stores/playerStore.ts` (new)
- `web/frontend/src/hooks/usePlayer.ts` (new)
- `web/frontend/src/hooks/useSyncWebSocket.ts` (modify - add playback/device handlers)

## Implementation Details

### 1. Create `stores/playerStore.ts`:

```typescript
interface PlayerState {
  // Playback
  currentTrack: Track | null
  queue: Track[]
  queueIndex: number
  trackStartedAt: number | null  // timestamp for position interpolation
  positionMs: number             // position at trackStartedAt (or paused position)
  isPlaying: boolean
  isMuted: boolean
  volume: number                 // 0-1, persisted to localStorage
  shuffleEnabled: boolean        // preference only - sent to backend on /play

  // Clock sync
  clockOffset: number            // server_time - Date.now(), updated on each playback:state

  // Scrobble tracking
  scrobbledThisPlaythrough: boolean  // reset on track change, prevents duplicate scrobbles

  // Devices
  thisDeviceId: string           // UUID, persisted to localStorage
  thisDeviceName: string         // auto-detected: `${platform} ${browser}`
  activeDeviceId: string | null
  availableDevices: Device[]

  // Derived
  isThisDeviceActive: boolean    // computed: activeDeviceId === thisDeviceId

  // Error handling
  playbackError: string | null   // 404, load failure, etc.

  // Gapless playback (hook for future)
  nextTrackPreloadUrl: string | null

  // Mobile constraints
  needsUserGesture: boolean      // iOS Safari requires tap to play
}

// Position helper (compute current position from state with clock sync)
function getCurrentPosition(state: PlayerState): number {
  if (!state.isPlaying || !state.trackStartedAt) return state.positionMs
  // Use clockOffset to correct for client/server time difference
  return state.positionMs + (Date.now() + state.clockOffset - state.trackStartedAt)
}

interface PlayerActions {
  // Playback control (calls API, waits for WebSocket confirmation - no optimistic updates)
  play(track: Track, context: PlayContext): Promise<void>  // shows loading state until confirmed
  pause(): Promise<void>
  resume(): Promise<void>
  next(): Promise<void>
  prev(): Promise<void>
  seek(positionMs: number): Promise<void>

  // Local state
  setMuted(muted: boolean): void
  toggleShuffle(): void  // toggles preference, triggers re-fetch with new shuffle value

  // Device management
  setActiveDevice(deviceId: string): void  // simplified: just "activeDevice"

  // State sync (called by WebSocket handler)
  // Computes clockOffset from server_time, resets scrobbledThisPlaythrough on track change
  syncState(state: PlaybackState & { server_time: number }): void
  syncDevices(devices: Device[]): void

  // Error handling
  setPlaybackError(error: string | null): void
  retryPlayback(): void

  // Gapless playback hook
  preloadNextTrack(): void

  // Scrobble/history hook
  onTrackPlayed(trackId: number, playedMs: number): void  // fires at 50% or 30s
}
```

**Device ID generation:**
- On first load, generate UUID v4, store in localStorage
- Persist across sessions so device identity is stable

**Device name detection:**
```typescript
const getDeviceName = (): string => {
  const ua = navigator.userAgent
  // Extract platform + browser (e.g., "Linux Chrome", "iPhone Safari")
  // Use simple regex or ua-parser-lite
}
```

### 2. Create `hooks/usePlayer.ts`:

```typescript
export function usePlayer() {
  const store = usePlayerStore()
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Initialize device on mount
  useEffect(() => {
    store.registerDevice()
  }, [])

  // Audio element - persist across device switches, never destroy
  useEffect(() => {
    // Create audio element once on mount
    if (!audioRef.current) {
      audioRef.current = new Audio()
      audioRef.current.volume = store.volume
    }

    // Cleanup on unmount only
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
        audioRef.current = null
      }
    }
  }, [])

  // Control playback based on device state and track
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    if (!store.isThisDeviceActive) {
      audio.pause()
      return
    }

    if (store.currentTrack) {
      const newSrc = `/api/tracks/${store.currentTrack.id}/stream`
      if (audio.src !== newSrc) {
        audio.src = newSrc
        audio.currentTime = getCurrentPosition(store) / 1000
      }
      // play() handled in mobile constraints effect below
    }
  }, [store.isThisDeviceActive, store.currentTrack?.id, store.isPlaying])

  // Position interpolation - no intervals needed!
  // UI components call getCurrentPosition(store) which computes from trackStartedAt
  // This is more efficient and eliminates drift across devices

  // Scrobble tracking - fire onTrackPlayed at 50% or 30s (once per playthrough)
  useEffect(() => {
    if (!store.isPlaying || !store.isThisDeviceActive || !store.currentTrack) return
    if (store.scrobbledThisPlaythrough) return  // Already scrobbled this track

    const duration = store.currentTrack.duration * 1000
    const threshold = Math.min(duration * 0.5, 30000)

    const checkScrobble = () => {
      const position = getCurrentPosition(store)
      if (position >= threshold && !store.scrobbledThisPlaythrough) {
        store.onTrackPlayed(store.currentTrack.id, position)
        // Note: syncState resets scrobbledThisPlaythrough on track change
      }
    }

    const timeout = setTimeout(checkScrobble, threshold - store.positionMs)
    return () => clearTimeout(timeout)
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough])

  // Gapless playback - preload next track 5s before end
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack) return

    const audio = audioRef.current
    if (!audio) return

    const onTimeUpdate = () => {
      if (audio.duration - audio.currentTime < 5) {
        store.preloadNextTrack()
      }
    }

    audio.addEventListener('timeupdate', onTimeUpdate)
    return () => audio.removeEventListener('timeupdate', onTimeUpdate)
  }, [store.currentTrack?.id])

  // Mobile audio constraints - iOS Safari requires user gesture
  useEffect(() => {
    if (!store.isThisDeviceActive) return
    if (!store.currentTrack || !store.isPlaying) return

    const audio = audioRef.current
    if (!audio) return

    audio.play().catch((err) => {
      if (err.name === 'NotAllowedError') {
        // iOS Safari blocked autoplay - need user gesture
        store.set({ needsUserGesture: true })
      } else {
        store.setPlaybackError(err.message)
      }
    })
  }, [store.isThisDeviceActive, store.currentTrack, store.isPlaying])

  // Error handling - retry or skip on audio load failure
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onError = () => {
      store.setPlaybackError(`Failed to load: ${store.currentTrack?.title}`)
      // Auto-skip to next track after 2s
      setTimeout(() => store.next(), 2000)
    }

    audio.addEventListener('error', onError)
    return () => audio.removeEventListener('error', onError)
  }, [store.currentTrack?.id])

  return store
}
```

### 3. Modify `hooks/useSyncWebSocket.ts`:

Add handlers for new message types:
- `playback:state` → call `playerStore.syncState()` (includes trackStartedAt for interpolation)
- `devices:updated` → call `playerStore.syncDevices()`

No position-only messages - clients interpolate from `trackStartedAt`.

On connect, send device registration:
```typescript
ws.send(JSON.stringify({
  type: 'device:register',
  id: playerStore.getState().thisDeviceId,
  name: playerStore.getState().thisDeviceName
}))
```

## Verification

1. Open app in browser, check localStorage for device ID
2. Check console for device name detection
3. Open Network tab, verify WebSocket sends `device:register` on connect
4. Open two tabs, verify both appear in device list
5. Call `playerStore.play()` from console, verify state syncs to other tab
6. Close one tab, verify device list updates (after 30s grace period)
