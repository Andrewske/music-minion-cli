---
task: 02-add-bucket-colored-borders
status: done
depends: [01-create-color-system]
files:
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Add Colored Borders to Buckets

## Context
Apply visual differentiation to buckets using colored borders. Active bucket (contains current track) shows full border, inactive buckets show left border only. Requires detecting which bucket contains the currently playing track.

## Files to Modify/Create
- web/frontend/src/components/organizer/Bucket.tsx (modify)
- web/frontend/src/pages/PlaylistOrganizer.tsx (modify)

## Implementation Details

### In Bucket.tsx (around line 120)

1. Import color helper:
```typescript
import { getBucketColor } from '../../constants/bucketColors';
```

2. Add new props to `BucketComponentProps`:
```typescript
interface BucketComponentProps {
  // ... existing props
  isActive?: boolean;  // NEW: true if bucket contains current track
}
```

3. Update the header div (line 122-128) to add colored borders:
```typescript
<div
  ref={setDropRef}
  data-testid={`bucket-header-${bucket.id}`}
  className={`flex items-center gap-2 px-3 py-2 transition-colors ${
    isOver ? 'bg-obsidian-accent/20 border-obsidian-accent' : ''
  } ${
    isActive ? 'border-4' : 'border-l-4'
  }`}
  style={{
    borderColor: getBucketColor(bucketIndex),
  }}
>
```

### In PlaylistOrganizer.tsx (around line 470-545)

1. Import color helper:
```typescript
import { getBucketColor } from '../constants/bucketColors';
```

2. Detect which bucket contains current track (add after line 100):
```typescript
// Build reverse lookup map for O(1) performance
const trackToBucketMap = useMemo(() => {
  const map = new Map<number, string>();
  buckets.forEach((bucket) => {
    bucket.track_ids.forEach((trackId) => {
      map.set(trackId, bucket.id);
    });
  });
  return map;
}, [buckets]);

// Detect which bucket contains the current track
const activeBucketId = currentTrack
  ? trackToBucketMap.get(currentTrack.id) ?? null
  : null;
```

3. Pass `isActive` prop to BucketComponent (in the BucketList section):
```typescript
<BucketList
  // ... existing props
  activeBucketId={activeBucketId}
  // ...
/>
```

4. Update BucketList.tsx to forward `isActive`:
```typescript
// In BucketList.tsx, update the map call (around line 50)
{sortedBuckets.map((bucket, index) => (
  <BucketComponent
    key={bucket.id}
    bucket={bucket}
    tracks={...}
    bucketIndex={index}
    totalBuckets={buckets.length}
    isActive={bucket.id === activeBucketId}  // NEW
    // ... other props
  />
))}
```

## Verification
- Import getBucketColor in both files without errors
- Each bucket header shows a colored left border (4px width)
- Colors cycle correctly for 10+ buckets (bucket 10 = same color as bucket 0)
- When a track is playing and assigned to a bucket, that bucket shows full border (all 4 sides)
- Inactive buckets show left border only
- Border color matches bucket's color from the palette
