---
task: 04-clickable-bucket-headers
status: done
depends: [02-add-bucket-colored-borders]
files:
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
  - path: web/frontend/src/components/organizer/BucketList.tsx
    action: modify
  - path: web/frontend/src/components/organizer/CurrentTrackBanner.tsx
    action: modify
---

# Implement Clickable Bucket Headers

## Context
Enable single-tap/click on bucket headers to assign the currently playing track to that bucket. Provides fast, discoverable interaction for both desktop and mobile users without requiring drag-and-drop or keyboard shortcuts.

**Note:** Task 05 will refactor the expand/collapse button handler to support mobile accordion behavior. Implement the expand/collapse stopPropagation pattern as shown below to maintain compatibility with Task 05's changes.

## Files to Modify/Create
- web/frontend/src/components/organizer/Bucket.tsx (modify)
- web/frontend/src/pages/PlaylistOrganizer.tsx (modify)
- web/frontend/src/components/organizer/BucketList.tsx (modify)
- web/frontend/src/components/organizer/CurrentTrackBanner.tsx (modify)

## Implementation Details

### 1. In Bucket.tsx (header section lines 122-220)

**Add new props:**
```typescript
interface BucketComponentProps {
  // ... existing props
  onHeaderClick?: () => void;  // NEW: Called when header is clicked
  isClickable?: boolean;       // NEW: true if current track exists
}
```

**Wrap header div with click handler:**
```typescript
<div
  ref={setDropRef}
  data-testid={`bucket-header-${bucket.id}`}
  onClick={onHeaderClick}
  className={`flex items-center gap-2 px-3 py-2 transition-colors ${
    isOver ? 'bg-obsidian-accent/20 border-obsidian-accent' : ''
  } ${
    isActive ? 'border-4' : 'border-l-4'
  } ${
    isClickable ? 'cursor-pointer hover:bg-white/5' : ''
  }`}
  style={{
    borderColor: getBucketColor(bucketIndex),
  }}
>
```

**Add stopPropagation to action buttons** (around line 165-218):
```typescript
{/* Each action button */}
<button
  type="button"
  onClick={(e) => {
    e.stopPropagation();  // Prevent header click
    onMove('up');
  }}
  // ... rest of button props
>

{/* Repeat for all action buttons: move up/down, shuffle, edit, delete */}
```

**Add stopPropagation to expand/collapse button** (line 130):
```typescript
<button
  type="button"
  onClick={(e) => {
    e.stopPropagation();  // Prevent header click
    setIsExpanded(!isExpanded);
  }}
  className="text-white/50 hover:text-white/80 transition-colors"
>
```

### 2. In PlaylistOrganizer.tsx

**Create header click handler** (add after line 148):
```typescript
const handleBucketHeaderClick = useCallback(
  async (bucketId: string): Promise<void> => {
    if (!currentTrack) return;

    // Find which bucket (if any) currently contains this track
    const currentBucketId = trackToBucketMap.get(currentTrack.id);

    // If already in target bucket, no-op
    if (currentBucketId === bucketId) return;

    await assignTrack(bucketId, currentTrack.id);

    // Only auto-advance if moving from unassigned
    if (!currentBucketId) {
      playNextUnassignedTrack(currentTrack.id);
    }
  },
  [currentTrack, trackToBucketMap, assignTrack, playNextUnassignedTrack]
);
```

**Pass handler to BucketList:**
```typescript
<BucketList
  // ... existing props
  onBucketHeaderClick={handleBucketHeaderClick}
  currentTrack={currentTrack}
  // ...
/>
```

### 3. In BucketList.tsx

**Add new props:**
```typescript
interface BucketListProps {
  // ... existing props
  onBucketHeaderClick?: (bucketId: string) => Promise<void>;
  currentTrack?: { id: number; title: string; artist: string | null } | null;
}
```

**Forward to BucketComponent** (around line 50):
```typescript
<BucketComponent
  key={bucket.id}
  bucket={bucket}
  // ... existing props
  onHeaderClick={() => onBucketHeaderClick?.(bucket.id)}
  isClickable={!!currentTrack}
/>
```

### 4. In CurrentTrackBanner.tsx (update hint text)

**Replace keyboard hints section** (lines 57-69):
```typescript
{/* Keyboard/tap hints */}
<div className="flex items-center justify-between text-xs">
  {/* Desktop hint */}
  <div className="hidden md:block text-white/40">
    Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">Shift</kbd> +{' '}
    <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">1</kbd>-<kbd className="px-1.5 py-0.5 bg-white/10 rounded text-white/60">{Math.min(buckets.length, 9)}</kbd> to assign to bucket
  </div>

  {/* Mobile hint */}
  <div className="md:hidden text-white/40">
    Tap bucket below to assign
  </div>

  {buckets.length === 0 && (
    <div className="text-amber-400/80">
      Create buckets first to assign tracks
    </div>
  )}
</div>
```

## Verification
- Clicking bucket header assigns current track to that bucket
- If current track already in bucket, clicking does nothing (no-op)
- Clicking action buttons (edit, delete, move, shuffle) does NOT trigger assignment
- Clicking expand/collapse icon does NOT trigger assignment
- Bucket header shows cursor pointer on hover when track is playing
- Bucket header has hover state (bg-white/5) when clickable
- Desktop shows "Press Shift+1-9..." hint
- Mobile (<768px) shows "Tap bucket below to assign" hint
- No current track → bucket headers not clickable (no cursor pointer)
