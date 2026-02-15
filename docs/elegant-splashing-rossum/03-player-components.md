---
task: 03-player-components
status: pending
depends: [02-frontend-player-store]
files:
  - path: web/frontend/src/components/player/PlayerBar.tsx
    action: create
  - path: web/frontend/src/components/player/DeviceSelector.tsx
    action: create
  - path: web/frontend/src/components/UpNext.tsx
    action: modify
  - path: web/frontend/src/routes/__root.tsx
    action: modify
---

# Player Components

## Context
Creates the visual player UI: a persistent bottom bar with controls, device selector dropdown, and updates UpNext to read from the store instead of polling. The PlayerBar is added to the root layout so it persists across all pages.

## Files to Modify/Create
- `web/frontend/src/components/player/PlayerBar.tsx` (new)
- `web/frontend/src/components/player/DeviceSelector.tsx` (new)
- `web/frontend/src/components/UpNext.tsx` (modify)
- `web/frontend/src/routes/__root.tsx` (modify)

## Implementation Details

### 1. Create `components/player/PlayerBar.tsx`:

Fixed bottom bar, always visible. Contains:
- **Left section:** Album art thumbnail, track title, artist
- **Center section:** Play/pause, next, prev buttons, progress bar with seek
- **Right section:** Device selector (speaker icon), schedule mode toggle, mute button

```typescript
export function PlayerBar() {
  const {
    currentTrack, isPlaying, isMuted, isThisDeviceActive,
    shuffleEnabled, playbackError, needsUserGesture, volume,
    pause, resume, next, prev, seek, setMuted, setVolume, toggleShuffle
  } = usePlayer()

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      switch (e.code) {
        case 'Space':
          e.preventDefault()
          isPlaying ? pause() : resume()
          break
        case 'ArrowRight':
          next()
          break
        case 'ArrowLeft':
          prev()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isPlaying, pause, resume, next, prev])

  // Progress calculation using interpolation
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    if (!currentTrack?.duration) {
      setProgress(0)
      return
    }
    if (!isPlaying) return

    const updateProgress = () => {
      const pos = getCurrentPosition(usePlayerStore.getState())
      setProgress((pos / (currentTrack.duration * 1000)) * 100)
    }

    updateProgress()
    const interval = setInterval(updateProgress, 250)  // UI update only, no state sync
    return () => clearInterval(interval)  // Cleanup to prevent duplicate intervals
  }, [currentTrack?.id, currentTrack?.duration, isPlaying])

  return (
    <div className="fixed bottom-0 left-0 right-0 h-16 bg-background border-t flex items-center px-4 gap-4">
      {/* Track info */}
      <div className="flex items-center gap-3 w-64">
        {currentTrack?.artwork && (
          <img src={currentTrack.artwork} className="w-10 h-10 rounded" />
        )}
        <div className="truncate">
          <div className="font-medium truncate">{currentTrack?.title ?? 'Not playing'}</div>
          <div className="text-sm text-muted-foreground truncate">{currentTrack?.artist}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex-1 flex flex-col items-center gap-1">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={prev}>
            <SkipBack className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={isPlaying ? pause : resume}>
            {isPlaying ? <Pause /> : <Play />}
          </Button>
          <Button variant="ghost" size="icon" onClick={next}>
            <SkipForward className="h-4 w-4" />
          </Button>
        </div>
        {/* Progress bar */}
        <Slider
          value={[progress]}
          max={100}
          onValueChange={([v]) => seek(v / 100 * currentTrack.duration * 1000)}
          className="w-96"
        />
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleShuffle}
          className={shuffleEnabled ? 'text-primary' : ''}
          title={shuffleEnabled ? 'Shuffle on' : 'Shuffle off'}
        >
          <Shuffle className="h-4 w-4" />
        </Button>
        <DeviceSelector />
        <Button variant="ghost" size="icon" onClick={() => setMuted(!isMuted)}>
          {isMuted ? <VolumeX /> : <Volume2 />}
        </Button>
        <Slider
          value={[isMuted ? 0 : volume * 100]}
          max={100}
          onValueChange={([v]) => setVolume(v / 100)}
          className="w-20"
        />
      </div>

      {/* Error indicator */}
      {playbackError && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full bg-destructive text-destructive-foreground text-xs px-2 py-1 rounded-t">
          {playbackError}
        </div>
      )}

      {/* iOS "tap to play" overlay */}
      {needsUserGesture && (
        <button
          onClick={resume}
          className="absolute inset-0 bg-black/50 flex items-center justify-center"
        >
          <span className="text-white">Tap to play</span>
        </button>
      )}

      {/* Playing on indicator (when not this device) */}
      {!isThisDeviceActive && currentTrack && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full bg-primary text-primary-foreground text-xs px-2 py-1 rounded-t">
          Playing on {activeDeviceName}
        </div>
      )}
    </div>
  )
}
```

### 2. Create `components/player/DeviceSelector.tsx`:

Dropdown showing available devices with indicators.

```typescript
export function DeviceSelector() {
  const { availableDevices, activeDeviceId, thisDeviceId, setTargetDevice } = usePlayer()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <Speaker className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Select Device</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {availableDevices.map(device => (
          <DropdownMenuItem
            key={device.id}
            onClick={() => setTargetDevice(device.id)}
          >
            <div className="flex items-center gap-2">
              {device.id === activeDeviceId && (
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              )}
              <span>{device.name}</span>
              {device.id === thisDeviceId && (
                <span className="text-xs text-muted-foreground">(this device)</span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

### 3. Modify `components/UpNext.tsx`:

Change from React Query polling to reading from playerStore.

```typescript
export function UpNext() {
  const { queue, queueIndex } = usePlayer()

  // Get upcoming tracks (next 5 after current)
  const upcoming = queue.slice(queueIndex + 1, queueIndex + 6)

  return (
    <div className="space-y-2">
      <h3 className="font-semibold">Up Next</h3>
      {upcoming.map((track, i) => (
        <TrackCard key={track.id} track={track} index={i + 1} compact />
      ))}
      {upcoming.length === 0 && (
        <p className="text-muted-foreground text-sm">Queue is empty</p>
      )}
    </div>
  )
}
```

Remove all React Query `useQuery` and polling logic.

### 4. Modify `routes/__root.tsx`:

Add PlayerBar to root layout, remove old radio audio element.

```typescript
export function Root() {
  return (
    <>
      <Outlet />
      <PlayerBar />  {/* Add this */}
      {/* Remove old radio <audio> element */}
    </>
  )
}
```

Add bottom padding to main content area so PlayerBar doesn't overlap:
```typescript
<main className="pb-20"> {/* Account for 64px player bar + margin */}
```

## Verification

1. Start app, verify PlayerBar appears at bottom
2. Verify it stays visible when navigating between pages
3. Click play/pause/next/prev, verify controls work
4. **Keyboard shortcuts**: Space=play/pause, →=next, ←=prev
5. Open device selector, verify this device shows with "(this device)"
6. Open two tabs, verify both devices appear in selector
7. Select other device as active, verify "Playing on..." indicator appears
8. Verify UpNext shows queue from store (not polling)
9. Toggle shuffle, verify queue re-fetches from backend
10. **Mobile test**: On iOS Safari, verify "Tap to play" appears on cross-device command
