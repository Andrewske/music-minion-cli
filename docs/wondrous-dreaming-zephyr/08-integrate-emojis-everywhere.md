# Integrate Emoji System Across All Track Components

## Files to Create
- `web/frontend/src/components/EmojiTrackActions.tsx` (new)

## Files to Modify
- `web/frontend/src/components/RadioPlayer.tsx` (modify)
- `web/frontend/src/components/TrackCard.tsx` (modify)
- `web/frontend/src/components/ComparisonView.tsx` (modify)
- `web/frontend/src/components/PlaylistTracksTable.tsx` (modify)
- `web/frontend/src/routes/__root.tsx` (modify - mini-display)

## Implementation Details

### Step 1: Create EmojiTrackActions Component

This is a **container component** that wraps EmojiReactions and EmojiPicker with state management.

Create `web/frontend/src/components/EmojiTrackActions.tsx`:

```tsx
import { useState } from 'react';
import { EmojiReactions } from './EmojiReactions';
import { EmojiPicker } from './EmojiPicker';
import { useTrackEmojis } from '../hooks/useTrackEmojis';

interface EmojiTrackActionsProps {
  track: { id: number; emojis?: string[] };
  onUpdate: (updatedTrack: { id: number; emojis?: string[] }) => void;
  compact?: boolean;
  className?: string;
}

/**
 * Self-contained emoji management for any track.
 * Handles state, API calls, optimistic updates, and error handling.
 *
 * Usage:
 *   <EmojiTrackActions track={track} onUpdate={setTrack} />
 */
export function EmojiTrackActions({
  track,
  onUpdate,
  compact = false,
  className = ''
}: EmojiTrackActionsProps): JSX.Element {
  const [showPicker, setShowPicker] = useState(false);

  const { addEmoji, removeEmoji, isAdding, isRemoving } = useTrackEmojis(track, onUpdate);

  const handleAddEmoji = async (emoji: string): Promise<void> => {
    await addEmoji(emoji);
    setShowPicker(false); // Close picker after adding
  };

  return (
    <>
      <EmojiReactions
        trackId={track.id}
        emojis={track.emojis || []}
        onRemove={removeEmoji}
        onAddClick={() => setShowPicker(true)}
        compact={compact}
        className={className}
        isAdding={isAdding}  // NEW: Disable "+ Add" while adding
        isRemoving={isRemoving}  // NEW: Visual feedback while removing
      />

      {showPicker && (
        <EmojiPicker
          onSelect={handleAddEmoji}
          onClose={() => setShowPicker(false)}
        />
      )}
    </>
  );
}
```

### Step 2: Integrate into RadioPlayer

Update `web/frontend/src/components/RadioPlayer.tsx`:

**Add imports:**
```tsx
import { EmojiTrackActions } from './EmojiTrackActions';
import { useState, useEffect } from 'react';
```

**Add keyboard shortcut state:**
```tsx
const [showEmojiPicker, setShowEmojiPicker] = useState(false);

// Keyboard shortcut: Ctrl/Cmd+E to open emoji picker
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.key === 'e' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      setShowEmojiPicker(true);
    }
  };

  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

**Insert component after track info, before progress bar:**
```tsx
{nowPlaying && (
  <>
    <div className="flex-1 min-w-0">
      <h2 className="text-lg font-semibold text-white truncate">
        {nowPlaying.track.title ?? 'Unknown Title'}
      </h2>
      <p className="text-slate-400 truncate">
        {nowPlaying.track.artist ?? 'Unknown Artist'}
      </p>
    </div>

    {/* NEW: Emoji Actions */}
    <div className="mt-4">
      <EmojiTrackActions
        track={nowPlaying.track}
        onUpdate={(updated) => updateNowPlayingTrack(updated)}
      />
    </div>

    {/* Existing progress bar */}
    <div className="mt-4">
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        {/* ... */}
      </div>
    </div>
  </>
)}
```

### Step 3: Integrate into TrackCard (Comparison View)

Update `web/frontend/src/components/TrackCard.tsx`:

**Add import:**
```tsx
import { EmojiTrackActions } from './EmojiTrackActions';
```

**Add prop:**
```tsx
interface TrackCardProps {
  onClick?: () => void;
  track: TrackInfo;
  isPlaying: boolean;
  className?: string;
  onArchive?: () => void;
  onWinner?: () => void;
  isLoading?: boolean;
  rankingMode?: 'global' | 'playlist';
  onTrackUpdate?: (track: TrackInfo) => void;  // NEW
}
```

**Insert after rating badge, before action buttons:**
```tsx
{/* Stats / Badges */}
<div className="pt-4 border-t border-slate-800 w-full flex justify-center">
  {renderRatingBadge(track.rating, track.wins, track.losses, track.comparison_count)}
</div>

{/* NEW: Emoji Actions */}
{onTrackUpdate && (
  <div className="pt-3 w-full flex justify-center">
    <EmojiTrackActions
      track={track}
      onUpdate={onTrackUpdate}
      className="justify-center"
    />
  </div>
)}
```

### Step 4: Add updateTrackInPair to Comparison Store

Update `web/frontend/src/stores/comparisonStore.ts`:

**Add to ComparisonActions interface:**
```tsx
interface ComparisonActions {
  // ... existing methods ...
  updateTrackInPair: (updated: TrackInfo) => void;  // NEW
}
```

**Add implementation:**
```tsx
updateTrackInPair: (updated: TrackInfo) => {
  set((state) => {
    if (!state.currentPair) return state;
    return {
      currentPair: {
        ...state.currentPair,
        track_a: state.currentPair.track_a.id === updated.id ? updated : state.currentPair.track_a,
        track_b: state.currentPair.track_b.id === updated.id ? updated : state.currentPair.track_b,
      }
    };
  });
},
```

### Step 5: Integrate into ComparisonView

Update `web/frontend/src/components/ComparisonView.tsx`:

**Import store method:**
```tsx
const { updateTrackInPair } = useComparisonStore();
```

**Pass to TrackCard:**
```tsx
<TrackCard
  track={currentPair.track_a}
  isPlaying={currentTrack?.id === currentPair.track_a.id && isPlaying}
  onArchive={() => handleArchive(currentPair.track_a)}
  onWinner={() => handleWinner(currentPair.track_a)}
  onClick={() => handleTrackTap(currentPair.track_a)}
  onTrackUpdate={updateTrackInPair}  // NEW
/>
```

### Step 5: Integrate into Mini-Display (Root Layout)

Update `web/frontend/src/routes/__root.tsx`:

**Add import:**
```tsx
import { EmojiTrackActions } from '../components/EmojiTrackActions';
```

**Add after artist/title in mini-display:**
```tsx
{/* Radio mini-display */}
{nowPlaying && (
  <div className="flex items-center gap-3">
    <button onClick={toggleMute} {...}>
      {/* Mute icon */}
    </button>

    <div className="flex flex-col">
      <div className="text-sm font-medium text-white truncate max-w-xs">
        {nowPlaying.track.artist} - {nowPlaying.track.title}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500">• {nowPlaying.station_name}</span>

        {/* NEW: Compact emoji display */}
        <EmojiTrackActions
          track={nowPlaying.track}
          onUpdate={(updated) => updateNowPlayingTrack(updated)}
          compact={true}
        />
      </div>
    </div>
  </div>
)}
```

### Step 6: Integrate into PlaylistTracksTable (Optional - Phase 2)

Update `web/frontend/src/components/PlaylistTracksTable.tsx`:

**Option A: Inline emoji display in title cell (Recommended)**
```tsx
// Modify title cell to show emojis inline
{
  id: 'title',
  accessorKey: 'title',
  header: 'Title',
  cell: (info) => {
    const track = info.row.original;
    return (
      <div className="flex items-center gap-2">
        <span className="truncate">{info.getValue() ?? '-'}</span>
        {/* Show first 3 emojis inline */}
        {track.emojis && track.emojis.length > 0 && (
          <div className="flex gap-1 shrink-0">
            {track.emojis.slice(0, 3).map((emoji, idx) => (
              <span key={idx} className="text-sm">
                {emoji}
              </span>
            ))}
            {track.emojis.length > 3 && (
              <span className="text-xs text-slate-500">
                +{track.emojis.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    );
  },
}
```

**Option B: Separate column with full emoji management**
```tsx
// Add new column
{
  id: 'emojis',
  header: 'Tags',
  cell: (info) => {
    const track = info.row.original;
    return (
      <EmojiTrackActions
        track={track}
        onUpdate={(updated) => {
          // Update track in parent state
        }}
        compact={true}
      />
    );
  },
  size: 120,
}
```

**Option C: Expandable row detail**
- Show emojis only when row is expanded
- Click row → shows full emoji management below
- More complex but cleaner for dense tables

## Acceptance Criteria

### Phase 1 (MVP) - Must Have
- [ ] RadioPlayer shows emoji badges below track info
- [ ] RadioPlayer "+ Add" button opens picker modal
- [ ] **Keyboard shortcut: Ctrl/Cmd+E opens emoji picker from anywhere**
- [ ] Clicking emoji badge removes it (with optimistic update + rollback on error)
- [ ] Adding emoji shows immediately (optimistic update)
- [ ] Toast errors appear on API failures
- [ ] TrackCard in ComparisonView shows emojis below rating badge
- [ ] Mini-display in header shows compact emoji badges
- [ ] All three contexts use same EmojiTrackActions component (DRY)
- [ ] **Emoji picker shows "Recently Used" section (last 10 emojis)**
- [ ] **Emoji count badges appear on all emojis in picker**

### Phase 2 (Nice to Have) - Optional
- [ ] PlaylistTracksTable shows emojis in table column
- [ ] Builder TrackQueueTable shows emojis (optional column or expandable row)
- [ ] Settings page shows track count per emoji (already in use_count)

### Testing
- [ ] Add emoji in RadioPlayer → appears in mini-display immediately
- [ ] Add emoji in ComparisonView TrackCard → persists when track appears again
- [ ] Remove emoji in one place → disappears everywhere
- [ ] Multiple emojis wrap correctly in all layouts
- [ ] Compact mode works in constrained spaces (mini-display, tables)
- [ ] Error handling: Failed add/remove shows toast and reverts UI

## Dependencies
- Task 04 (frontend setup) - provides useTrackEmojis hook, toast system
- Task 05 (EmojiReactions component)
- Task 06 (EmojiPicker component)

## Notes

**Why EmojiTrackActions wrapper?**
- Encapsulates picker state management (open/close)
- Handles hook integration (useTrackEmojis)
- Provides consistent behavior across all track displays
- Parent components just pass track + update callback - no emoji logic

**Track update patterns:**
- RadioPlayer: `updateNowPlayingTrack(updated)` from radioStore
- ComparisonView: Update track in comparisonStore
- Mini-display: Same as RadioPlayer (shared radioStore)
- Tables: Update item in parent array state

**Compact mode:**
- Smaller badges (text-base vs text-lg)
- No "+ Add" button (saves space)
- Useful for: header mini-display, table cells, crowded layouts
- Users can still click badges to remove emojis

**Keyboard Shortcut:**
- Ctrl+E (Windows/Linux) or Cmd+E (Mac) opens emoji picker
- Works globally whenever RadioPlayer is mounted
- Focus doesn't need to be on any specific element
- Prevents default browser behavior (common for "search" in some browsers)

**Emoji Display in Lists:**
- Shows first 3 emojis inline next to track title
- Additional count indicator ("+2") if more than 3
- Compact presentation doesn't clutter dense layouts
- Provides visual scanning capability for large libraries
