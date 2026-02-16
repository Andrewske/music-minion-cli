---
task: 06-home-page
status: done
depends: [05-stations-and-schedule]
files:
  - path: web/frontend/src/routes/index.tsx
    action: modify
  - path: web/frontend/src/components/HomePage.tsx
    action: create
---

# Home Page

## Context
Replaces the RadioPage with a simpler home layout focused on picking what to play. Shows current playback state prominently, with quick access to playlists and stations. The persistent PlayerBar handles playback controls, so the home page focuses on discovery/selection.

## Files to Modify/Create
- `web/frontend/src/routes/index.tsx` (modify - use new home page)
- `web/frontend/src/components/HomePage.tsx` (new)

## Implementation Details

### 1. Create `components/HomePage.tsx`:

```typescript
export function HomePage() {
  const { currentTrack, queue, queueIndex, isPlaying } = usePlayer()
  const { data: playlists } = useQuery(['playlists'], fetchPlaylists)
  const { data: stations } = useQuery(['stations'], fetchStations)

  return (
    <div className="container mx-auto p-6 space-y-8">
      {/* Now Playing - prominent section */}
      {currentTrack && (
        <section className="bg-card rounded-lg p-6">
          <h2 className="text-sm font-medium text-muted-foreground mb-4">Now Playing</h2>
          <div className="flex gap-6">
            {/* Large album art */}
            <div className="w-48 h-48 bg-muted rounded-lg overflow-hidden">
              {currentTrack.artwork && (
                <img src={currentTrack.artwork} className="w-full h-full object-cover" />
              )}
            </div>

            {/* Track info + queue preview */}
            <div className="flex-1">
              <h1 className="text-2xl font-bold">{currentTrack.title}</h1>
              <p className="text-lg text-muted-foreground">{currentTrack.artist}</p>
              {currentTrack.album && (
                <p className="text-sm text-muted-foreground">{currentTrack.album}</p>
              )}

              {/* Mini queue preview */}
              <div className="mt-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Up Next</h3>
                <div className="space-y-1">
                  {queue.slice(queueIndex + 1, queueIndex + 4).map((track, i) => (
                    <div key={track.id} className="text-sm flex items-center gap-2">
                      <span className="text-muted-foreground">{i + 1}.</span>
                      <span>{track.title}</span>
                      <span className="text-muted-foreground">- {track.artist}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Playlists grid */}
      <section>
        <h2 className="text-lg font-semibold mb-4">Playlists</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {playlists?.map(playlist => (
            <PlaylistCard key={playlist.id} playlist={playlist} />
          ))}
        </div>
      </section>

      {/* Stations quick access */}
      {stations && stations.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-4">Stations</h2>
          <div className="flex flex-wrap gap-2">
            {stations.map(station => (
              <StationChip key={station.id} station={station} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function PlaylistCard({ playlist }: { playlist: Playlist }) {
  const { play } = usePlayer()

  const handleClick = () => {
    if (playlist.tracks.length > 0) {
      play(playlist.tracks[0], {
        type: 'playlist',
        playlistId: playlist.id,
        startIndex: 0
      })
    }
  }

  return (
    <div
      onClick={handleClick}
      className="bg-card rounded-lg p-4 cursor-pointer hover:bg-accent transition-colors"
    >
      <div className="w-full aspect-square bg-muted rounded mb-3">
        {/* Playlist artwork or track collage */}
      </div>
      <h3 className="font-medium truncate">{playlist.name}</h3>
      <p className="text-sm text-muted-foreground">{playlist.tracks.length} tracks</p>
    </div>
  )
}

function StationChip({ station }: { station: Station }) {
  const { play } = usePlayer()

  const handleClick = async () => {
    const playlist = await fetchPlaylist(station.playlist_id)
    if (playlist.tracks.length > 0) {
      play(playlist.tracks[0], {
        type: 'playlist',
        playlistId: station.playlist_id,
        startIndex: 0
      })
    }
  }

  return (
    <button
      onClick={handleClick}
      className="px-4 py-2 bg-card rounded-full hover:bg-accent transition-colors"
    >
      {station.name}
    </button>
  )
}
```

### 2. Update `routes/index.tsx`:

Replace RadioPage with HomePage:

```typescript
import { HomePage } from '../components/HomePage'

export function Index() {
  return <HomePage />
}
```

### 3. Remove radio-specific elements:

Remove from home page:
- Icecast stream status indicators
- Liquidsoap connection status
- "Radio is streaming" banners
- Any RadioPlayer embedded in the page (player is now in PlayerBar)

### 4. Empty state:

When nothing is playing:
```typescript
{!currentTrack && (
  <section className="text-center py-12">
    <Music className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
    <h2 className="text-lg font-medium">Nothing playing</h2>
    <p className="text-muted-foreground">Select a playlist or station to start</p>
  </section>
)}
```

## Verification

1. Navigate to home page → verify new layout appears
2. With nothing playing → verify empty state shows
3. Click a playlist → verify it starts playing, Now Playing section appears
4. Click a station chip → verify it starts playing
5. Verify queue preview shows next 3 tracks
6. Verify no radio-specific UI elements remain
7. Verify PlayerBar is visible at bottom (from __root.tsx)
