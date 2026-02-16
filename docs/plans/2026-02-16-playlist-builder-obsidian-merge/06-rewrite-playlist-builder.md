---
task: 06-rewrite-playlist-builder
status: done
depends: [02-restyle-emoji-reactions, 03-restyle-waveform-player, 05-add-mobile-card-view]
files:
  - path: web/frontend/src/pages/PlaylistBuilder.tsx
    action: modify
---

# Rewrite PlaylistBuilder with Obsidian Layout

## Context
Replace PlaylistBuilder's slate grid layout with ObsidianBuilderMain's single-column black/amber design. This is the main integration task.

## Files to Modify
- web/frontend/src/pages/PlaylistBuilder.tsx (modify)

## Implementation Details

**Step 1: Remove unused imports**

Remove these imports:

```tsx
// REMOVE:
import FilterPanel from '../components/builder/FilterPanel';
```

**Step 2: Remove FilterPanel-related code from useBuilderSession destructure**

```tsx
// FROM:
const { session, addTrack, skipTrack, filters, updateFilters, startSession, isAddingTrack, isSkippingTrack } = useBuilderSession(playlistId);

// TO:
const { session, addTrack, skipTrack, startSession, isAddingTrack, isSkippingTrack } = useBuilderSession(playlistId);
```

**Step 3: Replace "no session" UI**

Replace the return block when `!session`:

```tsx
if (!session) {
  return (
    <div className="min-h-screen bg-black font-inter flex items-center justify-center">
      <div className="text-center">
        <p className="text-white/40 text-sm mb-8 font-sf-mono">{playlistName}</p>
        <button
          onClick={() => startSession.mutate(playlistId)}
          className="px-8 py-3 text-obsidian-accent border border-obsidian-accent/30
            hover:bg-obsidian-accent/10 transition-colors text-sm tracking-wider"
        >
          Begin
        </button>
      </div>
    </div>
  );
}
```

**Step 4: Replace main layout**

Replace the main return JSX with obsidian layout:

```tsx
return (
  <div className="min-h-screen bg-black font-inter text-white">
    <div className="max-w-6xl mx-auto px-4 md:px-8 py-4 md:py-8">
      <main>
        {currentTrack && queueIndex < candidates.length ? (
          <div className="space-y-6 md:space-y-12">
            {/* Player section - sticky on mobile */}
            <div className="sticky top-10 md:static z-10 bg-black pb-4 md:pb-0">
              {/* Track Display */}
              <div className="py-4 md:py-8">
                <p className="text-obsidian-accent text-sm font-sf-mono mb-2">{currentTrack.artist}</p>
                <h2 className="text-2xl md:text-4xl font-light text-white mb-2 md:mb-4">{currentTrack.title}</h2>
                {currentTrack.album && (
                  <p className="text-white/30 text-sm">{currentTrack.album}</p>
                )}

                {/* Metadata pills */}
                <div className="flex flex-wrap items-center gap-2 md:gap-4 mt-4 md:mt-6">
                  {currentTrack.bpm && (
                    <span className="text-white/40 text-xs font-sf-mono">{Math.round(currentTrack.bpm)} BPM</span>
                  )}
                  {currentTrack.key_signature && (
                    <span className="text-white/40 text-xs font-sf-mono">{currentTrack.key_signature}</span>
                  )}
                  {currentTrack.genre && (
                    <span className="text-white/40 text-xs font-sf-mono">{currentTrack.genre}</span>
                  )}
                  {currentTrack.year && (
                    <span className="text-white/40 text-xs font-sf-mono">{currentTrack.year}</span>
                  )}
                  <EmojiTrackActions
                    track={{ id: currentTrack.id, emojis: getTrackWithOverrides(currentTrack).emojis }}
                    onUpdate={handleTrackEmojiUpdate}
                  />
                </div>
              </div>

              {/* Waveform */}
              <div className="h-16 border-t border-b border-obsidian-border">
                <WaveformPlayer
                  track={{
                    id: currentTrack.id,
                    title: currentTrack.title,
                    artist: currentTrack.artist,
                    rating: currentTrack.elo_rating || 0,
                    comparison_count: 0,
                    wins: 0,
                    losses: 0,
                    has_waveform: true,
                  }}
                  isPlaying={isPlaying}
                  onTogglePlayPause={() => setIsPlaying(!isPlaying)}
                  onFinish={() => {
                    if (loopEnabled) {
                      setIsPlaying(false);
                      setTimeout(() => setIsPlaying(true), 100);
                    } else {
                      handleSkip();
                    }
                  }}
                />
              </div>

              {/* Loop toggle */}
              <div className="flex justify-center">
                <label className="flex items-center gap-3 text-white/30 text-sm cursor-pointer hover:text-white/50 transition-colors">
                  <input
                    type="checkbox"
                    checked={loopEnabled}
                    onChange={(e) => setLoopEnabled(e.target.checked)}
                    className="w-3 h-3 accent-obsidian-accent"
                  />
                  Loop
                </label>
              </div>

              {/* Actions */}
              <div className="flex gap-4 justify-center">
                <button
                  onClick={handleAdd}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="px-8 md:px-12 py-3 border border-obsidian-accent text-obsidian-accent
                    hover:bg-obsidian-accent hover:text-black disabled:opacity-30
                    transition-all text-sm tracking-wider"
                >
                  {isAddingTrack ? '...' : 'Add'}
                </button>
                <button
                  onClick={handleSkip}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="px-8 md:px-12 py-3 border border-white/20 text-white/60
                    hover:border-white/40 hover:text-white disabled:opacity-30
                    transition-all text-sm tracking-wider"
                >
                  {isSkippingTrack ? '...' : 'Skip'}
                </button>
              </div>
            </div>

            {/* Track Queue */}
            <TrackQueueTable
              tracks={candidates}
              queueIndex={queueIndex >= 0 ? queueIndex : 0}
              nowPlayingId={nowPlayingTrack?.id ?? null}
              onTrackClick={(track) => {
                if (track.id !== nowPlayingTrack?.id) setNowPlayingTrack(track);
              }}
              sorting={sorting}
              onSortingChange={setSorting}
              onLoadMore={() => fetchNextPage()}
              hasMore={hasNextPage ?? false}
              isLoadingMore={isFetchingNextPage}
            />
          </div>
        ) : (
          <div className="py-20 text-center">
            <p className="text-white/40 text-sm">
              {queueIndex >= candidates.length ? 'No more tracks' : 'Loading...'}
            </p>
          </div>
        )}
      </main>
    </div>
  </div>
);
```

**Step 5: Remove TrackDisplay and StatsPanel components**

Delete the `TrackDisplay` and `StatsPanel` function components at the bottom of the file if they exist.

## Verification

```bash
cd web/frontend && npm run dev
```

Navigate to playlist builder, verify full obsidian design with:
- Black background with amber accents
- Single-column layout
- Working waveform, add/skip buttons, emoji actions
- Mobile responsive layout

## Commit

```bash
git add web/frontend/src/pages/PlaylistBuilder.tsx
git commit -m "feat: rewrite PlaylistBuilder with obsidian layout"
```
