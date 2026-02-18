---
task: 01-refactor-homepage-layout
status: pending
depends: []
files:
  - path: web/frontend/src/components/HomePage.tsx
    action: modify
---

# Refactor HomePage.tsx Layout with Builder Components

## Context
Replace the minimal Home page layout with builder-style structure using TrackDisplay, WaveformSection, and TrackQueueTable components. This transforms the Home page into a full-featured now-playing view with the Obsidian theme aesthetic.

## Files to Modify
- `web/frontend/src/components/HomePage.tsx` (modify - refactor from 110 lines to ~200 lines)

## Implementation Details

### 1. Add New Imports

Add these imports at the top of `HomePage.tsx`:

```tsx
import { TrackDisplay } from './builder/TrackDisplay';
import { WaveformSection } from './builder/WaveformSection';
import { TrackQueueTable } from './builder/TrackQueueTable';
import type { SortingState } from '@tanstack/react-table';
import { useState, useCallback } from 'react';
```

### 2. Add New State Variables

Add these state hooks inside the `HomePage` component:

```tsx
const [loopEnabled, setLoopEnabled] = useState(false);
const [sorting, setSorting] = useState<SortingState>([]);
```

### 3. Extract Additional PlayerStore Actions

Update the playerStore destructuring to include:

```tsx
const {
  currentTrack,
  queue,
  queueIndex,
  isPlaying,
  currentContext,
  pause,
  resume,
  next,
  play
} = usePlayerStore();
```

### 4. Replace Main Layout Structure

Replace the entire return statement with this Obsidian-themed layout:

```tsx
return (
  <div className="min-h-screen bg-black font-inter text-white">
    <div className="max-w-6xl mx-auto px-4 md:px-8 py-4 md:py-8">
      {/* Header with context info */}
      <div className="mb-6">
        <p className="text-white/40 text-sm font-sf-mono mb-1">Now Playing</p>
        <h1 className="text-xl text-white/60">{getContextTitle(currentContext)}</h1>
      </div>

      {currentTrack ? (
        <div className="space-y-6 md:space-y-12">
          {/* Sticky player section on mobile */}
          <div className="sticky top-10 md:static z-10 bg-black pb-4 md:pb-0">
            <TrackDisplay track={currentTrack} />
            <WaveformSection
              track={currentTrack}
              isPlaying={isPlaying}
              loopEnabled={loopEnabled}
              onTogglePlayPause={() => isPlaying ? pause() : resume()}
              onLoopChange={setLoopEnabled}
              onFinish={handleWaveformFinish}
            />
          </div>

          {/* Queue Table */}
          <TrackQueueTable
            tracks={queue}
            queueIndex={queueIndex}
            nowPlayingId={currentTrack?.id ?? null}
            onTrackClick={handleTrackClick}
            sorting={sorting}
            onSortingChange={setSorting}
            onLoadMore={() => {}} // no-op - queue is fully loaded
            hasMore={false}
            isLoadingMore={false}
          />
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  </div>
);
```

### 5. Theme Application Notes

**Obsidian theme classes used:**
- Background: `bg-black`
- Borders: `border-obsidian-border`
- Accent: `text-obsidian-accent`
- Typography: `font-inter` (body), `font-sf-mono` (metadata)
- Spacing: `space-y-6 md:space-y-12`

**Responsive design:**
- Desktop: Full table view with virtual scrolling
- Mobile: Card view with sticky player section
- Breakpoint: `md:` prefix for tablet/desktop styles

## Verification

1. Start the web frontend: `music-minion --web`
2. Navigate to Home page (`/`)
3. Verify the layout compiles without TypeScript errors
4. Check that imports resolve correctly
5. Verify the layout structure renders (even if handlers aren't implemented yet)

**Expected outcome:**
- No TypeScript compilation errors
- Page renders with new structure
- Components are visible (even if not fully functional yet)
