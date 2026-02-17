# PlaylistBuilder Obsidian Merge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge ObsidianMinimalBuilder design into PlaylistBuilder and restyle universal components to obsidian theme.

**Architecture:** Replace PlaylistBuilder's slate-colored grid layout with ObsidianBuilderMain's single-column black/amber design. Restyle WaveformPlayer, TrackQueueTable, and EmojiReactions to match. Add mobile card view to TrackQueueTable.

**Tech Stack:** React, TailwindCSS, TanStack Table/Virtual, WaveSurfer.js

---

### Task 1: Clean Up EmojiReactions Debug Code

**Files:**
- Modify: `web/frontend/src/components/EmojiReactions.tsx:54-60`
- Modify: `web/frontend/src/components/EmojiTrackActions.tsx:26-28,39`

**Step 1: Remove debug overlay from EmojiReactions**

Delete lines 54-60 (the debug DOM manipulation):

```tsx
// DELETE THIS BLOCK:
// CRITICAL DEBUG: Write to page body to see output
if (typeof document !== 'undefined') {
  const debugEl = document.getElementById('emoji-debug') || document.createElement('div');
  debugEl.id = 'emoji-debug';
  debugEl.style.cssText = 'position:fixed;top:0;right:0;background:black;color:lime;padding:10px;zIndex:9999;fontSize:12px;maxWidth:400px';
  debugEl.innerHTML = `EMOJIS: ${JSON.stringify(emojis)}<br>LENGTHS: ${emojis.map(e => e?.length || 0).join(',')}`;
  if (!document.body.contains(debugEl)) document.body.appendChild(debugEl);
}
```

**Step 2: Remove console.logs from EmojiTrackActions**

Delete lines 26-28 and line 39:

```tsx
// DELETE THESE:
console.log('[EmojiTrackActions] RENDER - track:', track);
console.log('[EmojiTrackActions] track.emojis:', track.emojis);
// ...
console.log('[EmojiTrackActions] Passing to EmojiReactions - emojis:', emojisArray);
```

**Step 3: Verify app still works**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add web/frontend/src/components/EmojiReactions.tsx web/frontend/src/components/EmojiTrackActions.tsx
git commit -m "chore: remove debug code from emoji components"
```

---

### Task 2: Restyle EmojiReactions to Obsidian

**Files:**
- Modify: `web/frontend/src/components/EmojiReactions.tsx:80-95,99-111`

**Step 1: Update emoji button styling**

Replace the button className (around line 83-86):

```tsx
// FROM:
className={`
  ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1'}
  bg-slate-800 hover:bg-red-600 rounded-md transition-colors flex items-center justify-center
`}

// TO:
className={`
  relative group ${compact ? 'text-sm' : 'text-base'}
  leading-none hover:opacity-70 disabled:opacity-30 transition-opacity
`}
```

**Step 2: Add × indicator on hover**

After `<EmojiDisplay ... />` (around line 93), add:

```tsx
<span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
  <span className="text-obsidian-accent text-xs font-bold">×</span>
</span>
```

**Step 3: Update add button styling**

Replace add button className (around line 103-107):

```tsx
// FROM:
className={`text-2xl font-normal transition-colors ${
  isAdding
    ? 'text-emerald-500 opacity-50 cursor-not-allowed'
    : 'text-emerald-500 hover:text-emerald-400'
}`}

// TO:
className={`text-sm font-bold transition-colors ${
  isAdding
    ? 'text-green-500 opacity-30 cursor-not-allowed'
    : 'text-green-500 hover:text-green-400'
}`}
```

**Step 4: Verify styling**

Run: `cd web/frontend && npm run dev`
Navigate to a page with emoji actions, verify obsidian styling

**Step 5: Commit**

```bash
git add web/frontend/src/components/EmojiReactions.tsx
git commit -m "style: restyle EmojiReactions to obsidian theme"
```

---

### Task 3: Restyle WaveformPlayer to Obsidian

**Files:**
- Modify: `web/frontend/src/components/WaveformPlayer.tsx:78-92,114`

**Step 1: Update play button styling**

Replace play button (lines 78-92):

```tsx
// FROM:
<button
  onClick={onTogglePlayPause || togglePlayPause}
  className="flex-shrink-0 w-10 h-10 ml-3 mr-2 bg-emerald-500 text-white rounded-full flex items-center justify-center hover:bg-emerald-400 shadow-lg transition-colors"
  aria-label={isPlaying ? 'Pause' : 'Play'}
>

// TO:
<button
  onClick={onTogglePlayPause || togglePlayPause}
  className="w-8 h-8 flex items-center justify-center text-obsidian-accent hover:text-white transition-colors"
  aria-label={isPlaying ? 'Pause' : 'Play'}
>
```

**Step 2: Update icon sizes**

Change icon classes from `w-5 h-5` to `w-4 h-4` (lines 84, 88)

**Step 3: Update time display styling**

Replace time display (line 114):

```tsx
// FROM:
<div className="absolute bottom-1 right-2 z-10 text-[10px] font-mono text-emerald-400/80 bg-slate-900/80 px-1 rounded pointer-events-none">

// TO:
<span className="text-white/30 text-xs font-sf-mono w-20 text-right">
```

Change content format:
```tsx
// FROM:
{formatTime(currentTime)} / {formatTime(duration)}

// TO (same but outside the div, as flex sibling):
```

**Step 4: Restructure layout to match obsidian**

The overall structure should become:

```tsx
<div className="flex items-center w-full h-full gap-4">
  {/* Play button */}
  <button ...>...</button>

  {/* Waveform container */}
  <div className="flex-1 h-full relative">
    {error && <div className="absolute inset-0 z-20 ...">...</div>}
    <div ref={containerRef} className="w-full h-full" />
  </div>

  {/* Time display */}
  <span className="text-white/30 text-xs font-sf-mono w-20 text-right">
    {formatTime(currentTime)} / {formatTime(duration)}
  </span>
</div>
```

**Step 5: Verify waveform works**

Run: `cd web/frontend && npm run dev`
Navigate to playlist builder, verify waveform plays and displays correctly

**Step 6: Commit**

```bash
git add web/frontend/src/components/WaveformPlayer.tsx
git commit -m "style: restyle WaveformPlayer to obsidian theme"
```

---

### Task 4: Restyle TrackQueueTable to Obsidian

**Files:**
- Modify: `web/frontend/src/components/builder/TrackQueueTable.tsx:152-165,180-187,236-237`

**Step 1: Update row highlight classes**

Replace `getRowClasses` function (lines 152-165):

```tsx
const getRowClasses = (index: number, trackId: number): string => {
  const isQueue = index === queueIndex;
  const isPlaying = trackId === nowPlayingId;

  let classes = 'cursor-pointer hover:bg-white/5 transition-colors ';

  if (isPlaying) {
    classes += 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent ';
  } else if (isQueue) {
    classes += 'bg-white/5 ';
  }

  return classes;
};
```

**Step 2: Update container styling**

Replace container div (line 180):

```tsx
// FROM:
<div className="bg-slate-800 rounded-lg overflow-hidden">

// TO:
<div className="border-t border-obsidian-border">
```

**Step 3: Update header styling**

Replace thead (line 187):

```tsx
// FROM:
<thead className="bg-slate-700" style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}>

// TO:
<thead className="border-b border-obsidian-border" style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}>
```

**Step 4: Update header cell styling**

Replace th className (lines 193):

```tsx
// FROM:
className="px-3 py-2 text-left cursor-pointer hover:bg-slate-600 select-none"

// TO:
className={`px-3 py-2 text-left cursor-pointer select-none text-xs tracking-wider uppercase transition-colors
  ${sorting.find(s => s.id === header.id) ? 'text-obsidian-accent' : 'text-white/30 hover:text-white/60'}`}
```

**Step 5: Update cell styling**

Replace td className (line 236-237):

```tsx
// FROM:
className="px-3 py-2 border-b border-slate-700 overflow-hidden"

// TO:
className="px-3 py-2 border-b border-obsidian-border/50 overflow-hidden text-white/50"
```

**Step 6: Update loading indicator**

Replace loading div (lines 255-257):

```tsx
// FROM:
<div className="text-center py-2 text-slate-400 text-sm">

// TO:
<div className="w-full py-2 text-white/30 text-xs text-center">
```

**Step 7: Verify table styling**

Run: `cd web/frontend && npm run dev`
Navigate to playlist builder, verify table has obsidian styling

**Step 8: Commit**

```bash
git add web/frontend/src/components/builder/TrackQueueTable.tsx
git commit -m "style: restyle TrackQueueTable to obsidian theme"
```

---

### Task 5: Add Mobile Card View to TrackQueueTable

**Files:**
- Modify: `web/frontend/src/components/builder/TrackQueueTable.tsx`

**Step 1: Import TrackQueueCard**

Add import at top:

```tsx
import { TrackQueueCard } from '../playlist-builder/TrackQueueCard';
```

**Step 2: Wrap desktop table in hidden md:block**

Wrap the existing table structure:

```tsx
{/* Desktop: Table view */}
<div className="hidden md:block">
  {/* existing table code */}
</div>
```

**Step 3: Add mobile card view**

After the desktop div, add:

```tsx
{/* Mobile: Card view */}
<div className="md:hidden">
  {/* Sort selector */}
  <div className="flex items-center gap-2 py-2 border-b border-obsidian-border">
    <span className="text-white/30 text-xs">Sort:</span>
    <select
      value={sorting[0]?.id || 'artist'}
      onChange={(e) => {
        const newSorting = [{ id: e.target.value, desc: sorting[0]?.desc ?? false }];
        onSortingChange(newSorting);
      }}
      className="bg-black border border-obsidian-border px-2 py-1 text-white text-xs rounded"
    >
      {columns.map(col => (
        <option key={col.id} value={col.id}>{String(col.header)}</option>
      ))}
    </select>
    <button
      onClick={() => onSortingChange([{ id: sorting[0]?.id || 'artist', desc: !sorting[0]?.desc }])}
      className="text-obsidian-accent text-xs"
    >
      {sorting[0]?.desc ? '↓' : '↑'}
    </button>
  </div>

  {/* Cards */}
  <div className="max-h-[40vh] overflow-y-auto">
    {tracks.map((track, idx) => (
      <TrackQueueCard
        key={track.id}
        track={track}
        isQueue={idx === queueIndex}
        isPlaying={track.id === nowPlayingId}
        onClick={() => onTrackClick(track)}
      />
    ))}
  </div>
</div>
```

**Step 4: Move load more button outside both views**

Ensure the "load more" button is after both mobile and desktop views.

**Step 5: Verify mobile view**

Run: `cd web/frontend && npm run dev`
Use browser dev tools to test mobile viewport, verify card view works

**Step 6: Commit**

```bash
git add web/frontend/src/components/builder/TrackQueueTable.tsx
git commit -m "feat: add mobile card view to TrackQueueTable"
```

---

### Task 6: Rewrite PlaylistBuilder with Obsidian Layout

**Files:**
- Modify: `web/frontend/src/pages/PlaylistBuilder.tsx`

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

Replace the return block when `!session` (lines 193-207):

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

Replace the main return JSX (lines 214-334) with obsidian layout:

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

Delete the `TrackDisplay` and `StatsPanel` function components at the bottom of the file (lines 337-375).

**Step 6: Verify PlaylistBuilder works**

Run: `cd web/frontend && npm run dev`
Navigate to playlist builder, verify full obsidian design

**Step 7: Commit**

```bash
git add web/frontend/src/pages/PlaylistBuilder.tsx
git commit -m "feat: rewrite PlaylistBuilder with obsidian layout"
```

---

### Task 7: Delete ObsidianMinimalBuilder

**Files:**
- Delete: `web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx`

**Step 1: Search for imports of ObsidianMinimalBuilder**

Run: `grep -r "ObsidianMinimalBuilder" web/frontend/src/`

If any imports exist, remove them.

**Step 2: Delete the file**

```bash
rm web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx
```

**Step 3: Verify build succeeds**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete ObsidianMinimalBuilder (merged into PlaylistBuilder)"
```

---

### Task 8: Final Verification

**Step 1: Run full build**

```bash
cd web/frontend && npm run build
```

**Step 2: Test playlist builder flow**

1. Start dev server: `npm run dev`
2. Navigate to a manual playlist
3. Verify "Begin" button appears with obsidian styling
4. Start session, verify track display
5. Test waveform playback
6. Test add/skip buttons
7. Test emoji actions
8. Test track queue (desktop table view)
9. Test mobile view (card layout)
10. Verify loop toggle works

**Step 3: Commit any final fixes**

If needed.
