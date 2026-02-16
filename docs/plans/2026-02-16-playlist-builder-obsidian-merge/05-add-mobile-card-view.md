---
task: 05-add-mobile-card-view
status: pending
depends: [04-restyle-track-queue-table]
files:
  - path: web/frontend/src/components/builder/TrackQueueTable.tsx
    action: modify
---

# Add Mobile Card View to TrackQueueTable

## Context
Add responsive mobile card view using TrackQueueCard component. Table visible on md+, cards on mobile with sort selector.

## Files to Modify
- web/frontend/src/components/builder/TrackQueueTable.tsx (modify)

## Implementation Details

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

## Verification

```bash
cd web/frontend && npm run dev
```

Use browser dev tools to test mobile viewport, verify card view works with sort selector.

## Commit

```bash
git add web/frontend/src/components/builder/TrackQueueTable.tsx
git commit -m "feat: add mobile card view to TrackQueueTable"
```
