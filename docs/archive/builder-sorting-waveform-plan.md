# Playlist Builder: Sorting Controls & Waveform Visualization

## Overview

Finish the web playlist builder by adding two missing features:
1. **Sorting Controls** - Allow users to sort candidates by field (artist, title, year, bpm, elo_rating)
2. **Waveform Visualization** - Replace basic `<audio>` with WaveSurfer for visual scrubbing

Both features already have infrastructure in place - this plan connects existing pieces.

## Current State

**Sorting:**
- Blessed CLI: Full sorting with dropdown (artist, title, year, bpm) - client-side via `PlaylistBuilderState.sort_field/sort_direction`
- Web backend: Returns candidates with `ORDER BY RANDOM()` - no sorting API
- Web frontend: No sorting UI

**Waveform:**
- `WaveformPlayer` component exists and works (`web/frontend/src/components/WaveformPlayer.tsx`)
- `useWavesurfer` hook handles all audio logic (`web/frontend/src/hooks/useWavesurfer.tsx`)
- PlaylistBuilder uses basic `<audio ref={audioRef}>` with manual controls
- Backend `/api/tracks/{id}/stream` and `/api/tracks/{id}/waveform` endpoints exist

---

## Task 1: Add Sort State to Builder Hook

**File:** `web/frontend/src/hooks/useBuilderSession.ts`

Add sort state management alongside existing filter state:

```typescript
// Add to existing imports
import { useState } from 'react';

// Add type at top of file
export type SortField = 'artist' | 'title' | 'year' | 'bpm' | 'elo_rating';
export type SortDirection = 'asc' | 'desc';

export function useBuilderSession(playlistId: number | null) {
  // ... existing code ...

  // Add local sort state (client-side sorting, no backend needed)
  const [sortField, setSortField] = useState<SortField>('artist');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Add to return
  return {
    // ... existing ...
    sortField,
    sortDirection,
    setSortField,
    setSortDirection,
  };
}
```

**Rationale:** Client-side sorting is sufficient since we fetch ~100 candidates. No backend changes needed.

**Acceptance Criteria:**
- [ ] Sort state exported from hook
- [ ] TypeScript types for SortField and SortDirection

---

## Task 2: Create SortControl Component

**File:** `web/frontend/src/components/builder/SortControl.tsx` (new)

```typescript
import type { SortField, SortDirection } from '../../hooks/useBuilderSession';

interface SortControlProps {
  sortField: SortField;
  sortDirection: SortDirection;
  onSortFieldChange: (field: SortField) => void;
  onSortDirectionChange: (direction: SortDirection) => void;
}

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'artist', label: 'Artist' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
  { value: 'bpm', label: 'BPM' },
  { value: 'elo_rating', label: 'Rating' },
];

export function SortControl({
  sortField,
  sortDirection,
  onSortFieldChange,
  onSortDirectionChange,
}: SortControlProps) {
  const toggleDirection = () => {
    onSortDirectionChange(sortDirection === 'asc' ? 'desc' : 'asc');
  };

  const directionIcon = sortDirection === 'asc' ? '↑' : '↓';
  const directionLabel = sortField === 'artist' || sortField === 'title'
    ? (sortDirection === 'asc' ? 'A→Z' : 'Z→A')
    : directionIcon;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-slate-400">Sort:</span>
      <select
        value={sortField}
        onChange={(e) => onSortFieldChange(e.target.value as SortField)}
        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <button
        onClick={toggleDirection}
        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-white"
        title={`Sort ${sortDirection === 'asc' ? 'ascending' : 'descending'}`}
      >
        {directionLabel}
      </button>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Dropdown with 5 sort options
- [ ] Direction toggle button with visual indicator
- [ ] Proper TypeScript typing

---

## Task 3: Add Sort Logic to PlaylistBuilder

**File:** `web/frontend/src/pages/PlaylistBuilder.tsx`

Modify to use sorted candidates instead of random order:

```typescript
// Add import
import { SortControl } from '../components/builder/SortControl';
import type { SortField, SortDirection } from '../hooks/useBuilderSession';

// In component, add sorting
const {
  // ... existing destructuring ...
  sortField,
  sortDirection,
  setSortField,
  setSortDirection,
} = useBuilderSession(playlistId);

// Add candidates query for sorted list (optional - if we want list view)
const { data: candidatesData } = useQuery({
  queryKey: ['builder-candidates', playlistId, sortField, sortDirection],
  queryFn: () => playlistId ? builderApi.getCandidates(playlistId, 100, 0) : null,
  enabled: !!playlistId && !!session,
  select: (data) => {
    if (!data?.candidates) return data;
    const sorted = [...data.candidates].sort((a, b) => {
      const aVal = a[sortField] ?? '';
      const bVal = b[sortField] ?? '';
      const cmp = typeof aVal === 'number'
        ? aVal - (bVal as number)
        : String(aVal).localeCompare(String(bVal));
      return sortDirection === 'asc' ? cmp : -cmp;
    });
    return { ...data, candidates: sorted };
  },
});

// Add to UI (in the header area, above track display)
<div className="flex justify-between items-center mb-4">
  <h2 className="text-xl font-semibold">Building: {playlistName}</h2>
  <SortControl
    sortField={sortField}
    sortDirection={sortDirection}
    onSortFieldChange={setSortField}
    onSortDirectionChange={setSortDirection}
  />
</div>
```

**Alternative: Sequential Candidates**
If we want sorted sequential playback (not random), modify `getNextCandidate`:

```typescript
// Fetch sorted candidates once, iterate through them
const [candidateIndex, setCandidateIndex] = useState(0);

const handleAdd = async () => {
  // ... add track ...
  setCandidateIndex(prev => prev + 1);
};

const handleSkip = async () => {
  // ... skip track ...
  setCandidateIndex(prev => prev + 1);
};

// Current track from sorted list
const currentTrack = candidatesData?.candidates[candidateIndex] ?? null;
```

**Decision needed:** Random vs Sequential sorted playback?

**Acceptance Criteria:**
- [ ] SortControl visible in builder header
- [ ] Changing sort re-orders candidates
- [ ] Sort persists during session

---

## Task 4: Integrate WaveformPlayer Component

**File:** `web/frontend/src/pages/PlaylistBuilder.tsx`

Replace basic audio element with WaveformPlayer:

```typescript
// Add import
import { WaveformPlayer } from '../components/WaveformPlayer';

// Remove
const audioRef = useRef<HTMLAudioElement>(null);

// Add state for playback control
const [isPlaying, setIsPlaying] = useState(true); // Auto-play by default

// Replace audio element and auto-play logic
// REMOVE this entire useEffect:
// useEffect(() => {
//   if (currentTrack && audioRef.current) { ... }
// }, [currentTrack?.id]);

// REPLACE <audio ref={audioRef} /> with:
{currentTrack && (
  <div className="h-20 mb-6">
    <WaveformPlayer
      track={{
        id: currentTrack.id,
        title: currentTrack.title,
        artist: currentTrack.artist,
      }}
      isPlaying={isPlaying}
      onTogglePlayPause={() => setIsPlaying(!isPlaying)}
      onFinish={() => {
        // Loop: restart playback
        setIsPlaying(false);
        setTimeout(() => setIsPlaying(true), 100);
      }}
    />
  </div>
)}
```

**Track Change Handling:**
```typescript
// Auto-play new tracks
useEffect(() => {
  if (currentTrack) {
    setIsPlaying(true);
  }
}, [currentTrack?.id]);
```

**Acceptance Criteria:**
- [ ] Waveform displays for current track
- [ ] Play/pause button works
- [ ] Clicking waveform seeks to position
- [ ] Time display shows current/total
- [ ] Auto-plays when track changes
- [ ] Loops on finish (or auto-advances - your preference)

---

## Task 5: Handle Loop vs Auto-Advance

**Decision Point:** Should tracks loop or auto-advance?

**Option A: Loop (current blessed CLI behavior)**
```typescript
onFinish={() => {
  // Restart from beginning
  setIsPlaying(false);
  setTimeout(() => setIsPlaying(true), 100);
}}
```

**Option B: Auto-skip on finish**
```typescript
onFinish={() => {
  // Automatically skip to next
  handleSkip();
}}
```

**Option C: Configurable toggle**
```typescript
const [loopEnabled, setLoopEnabled] = useState(true);

onFinish={() => {
  if (loopEnabled) {
    setIsPlaying(false);
    setTimeout(() => setIsPlaying(true), 100);
  } else {
    handleSkip();
  }
}}

// Add toggle in UI
<label className="flex items-center gap-2 text-sm text-slate-400">
  <input
    type="checkbox"
    checked={loopEnabled}
    onChange={(e) => setLoopEnabled(e.target.checked)}
    className="rounded"
  />
  Loop track
</label>
```

**Recommendation:** Option C (configurable) - matches user expectations for audition workflow.

---

## Task 6: Keyboard Shortcuts for Waveform

**File:** `web/frontend/src/pages/PlaylistBuilder.tsx`

Add seek shortcuts (0-9 for percentage, arrow keys for ±10s):

```typescript
// Add keyboard listener
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Don't capture if typing in input
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      return;
    }

    // 0-9: Jump to percentage
    if (e.key >= '0' && e.key <= '9') {
      const percent = parseInt(e.key) * 10;
      // Dispatch event for useWavesurfer to handle
      window.dispatchEvent(new CustomEvent('music-minion-seek-percent', { detail: percent }));
    }

    // Space: Toggle play/pause
    if (e.key === ' ') {
      e.preventDefault();
      setIsPlaying(prev => !prev);
    }
  };

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, []);
```

**Update useWavesurfer to handle percentage seek:**
```typescript
// In useWavesurfer.ts, add listener
useEffect(() => {
  const handleSeekPercent = (e: CustomEvent<number>) => {
    seekToPercent(e.detail);
  };

  window.addEventListener('music-minion-seek-percent', handleSeekPercent as EventListener);
  return () => window.removeEventListener('music-minion-seek-percent', handleSeekPercent as EventListener);
}, [seekToPercent]);
```

**Acceptance Criteria:**
- [ ] Space bar toggles play/pause
- [ ] Number keys 0-9 seek to percentage
- [ ] Arrow keys seek ±10 seconds (already implemented via IPC)

---

## File Summary

| File | Action | Lines |
|------|--------|-------|
| `hooks/useBuilderSession.ts` | Modify | +15 |
| `components/builder/SortControl.tsx` | Create | ~60 |
| `pages/PlaylistBuilder.tsx` | Modify | +40, -30 |
| `hooks/useWavesurfer.ts` | Modify | +10 |

**Total: ~95 new lines, ~30 removed**

---

## Testing Checklist

### Sorting
- [ ] Default sort is artist ascending
- [ ] Changing field re-sorts candidates
- [ ] Direction toggle works (A→Z / Z→A for text, ↑/↓ for numbers)
- [ ] BPM sorts numerically (not alphabetically)
- [ ] Year sorts numerically
- [ ] ELO rating sorts numerically
- [ ] Missing values sort to end

### Waveform
- [ ] Waveform loads and displays
- [ ] Play/pause button works
- [ ] Clicking waveform seeks
- [ ] Time display updates during playback
- [ ] Error state shows with retry button
- [ ] Track change loads new waveform
- [ ] Loop/auto-advance works as configured

### Keyboard Shortcuts
- [ ] Space toggles play/pause
- [ ] 0-9 seeks to percentage
- [ ] Shortcuts don't fire when typing in filter input

### Integration
- [ ] Add track → next track loads → waveform resets
- [ ] Skip track → next track loads → waveform resets
- [ ] Sorting + filtering work together
- [ ] Session resumes with correct sort state

---

## Implementation Order

1. **Task 1** - Add sort state to hook (5 min)
2. **Task 2** - Create SortControl component (15 min)
3. **Task 3** - Integrate sorting in PlaylistBuilder (20 min)
4. **Task 4** - Replace audio with WaveformPlayer (20 min)
5. **Task 5** - Add loop/auto-advance toggle (10 min)
6. **Task 6** - Keyboard shortcuts (15 min)

**Estimated total: ~1.5 hours**

---

## Future Enhancements (Out of Scope)

- Persist sort preference per playlist in database
- Multi-column sorting
- Candidate list view (see all candidates, not just current)
- Waveform zoom controls
- Playback speed control
- A/B loop for section repeat
