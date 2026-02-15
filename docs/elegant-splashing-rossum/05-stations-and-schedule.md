---
task: 05-stations-and-schedule
status: pending
depends: [04-queue-and-context]
files:
  - path: web/frontend/src/components/StationsList.tsx
    action: modify
---

# Stations (Quick Play Presets)

## Context
Simplifies the station model (removing Liquidsoap-specific features). Stations become "quick play" presets - clicking one starts its playlist. Schedule mode has been deferred to a future iteration.

## Files to Modify/Create
- `web/frontend/src/components/StationsList.tsx` (modify)

## Implementation Details

### 1. Simplify station model:

Remove source filters and schedule (playlists are now source-specific themselves):

```python
# Station model (backend) - simplified
class Station(BaseModel):
    id: int
    name: str
    playlist_id: int
    shuffle_enabled: bool = True
```

### 2. Update StationsList.tsx:

Change "Activate" to "Play" - clicking a station plays its playlist.

```typescript
export function StationsList() {
  const { play, shuffleEnabled } = usePlayer()
  const { data: stations } = useQuery(['stations'], fetchStations)

  const handlePlayStation = async (station: Station) => {
    // Fetch first track of playlist, play with playlist context
    const playlist = await fetchPlaylist(station.playlist_id)
    if (playlist.tracks.length > 0) {
      play(playlist.tracks[0], {
        type: 'playlist',
        playlistId: station.playlist_id,
        startIndex: 0,
        shuffle: station.shuffle_enabled ?? shuffleEnabled
      })
    }
  }

  return (
    <div className="space-y-2">
      <h3 className="font-semibold">Stations</h3>
      {stations?.map(station => (
        <div
          key={station.id}
          className="flex items-center justify-between p-2 rounded hover:bg-accent cursor-pointer"
          onClick={() => handlePlayStation(station)}
        >
          <div>
            <div className="font-medium">{station.name}</div>
            <div className="text-sm text-muted-foreground">
              {station.shuffle_enabled ? 'Shuffle' : 'Sequential'}
            </div>
          </div>
          <Button variant="ghost" size="icon">
            <Play className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  )
}
```

Remove:
- Source filter UI
- "Activate/Deactivate" toggle
- Liquidsoap-specific status indicators
- Schedule configuration UI (deferred)

## Verification

1. Create a station with a playlist
2. Click station → verify playlist starts playing with station's shuffle preference
3. Verify no radio-specific UI elements remain
4. Verify station edit modal still works for basic fields (name, playlist)

## Deferred: Schedule Mode

Schedule mode (automatic station switching based on time) has been deferred to reduce v1 scope. The architecture supports adding it later:
- Add `schedule: ScheduleSlot[]` field to Station model
- Add `/api/player/schedule/current` endpoint
- Add `scheduleMode: boolean` to playerStore
- Add minute-by-minute polling when enabled

This can be implemented when/if the feature is actually needed.
