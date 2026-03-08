---
task: 07-bucket-header-indicator
status: merged
depends: [05-frontend-hook]
merged_into: 06-bucket-edit-popup
files:
  - path: web/frontend/src/components/organizer/BucketList.tsx
    action: modify
---

# UI: Bucket Header Linked Playlist Indicator

**MERGED INTO TASK 06** - See [06-bucket-edit-popup.md](./06-bucket-edit-popup.md) for combined implementation.

## Original Context
Visual indicator showing which playlist a bucket is linked to. Displays the linked playlist name in parentheses after the track count, styled with the bucket's color.

## Files to Modify/Create
- web/frontend/src/components/organizer/BucketList.tsx (modify)

## Implementation Details

### Current bucket header format:
`{emoji} {name} ({count})`

### New format when linked:
`{emoji} {name} ({count}) (Playlist Name)`

Where "Playlist Name" is styled with the bucket's color.

### Implementation in BucketHeader or BucketList:

```tsx
function BucketHeader({ bucket, ... }: BucketHeaderProps) {
  // Get bucket color (from emoji or default)
  const bucketColor = getBucketColor(bucket.emoji_id);

  return (
    <div className="flex items-center gap-2">
      {bucket.emoji_id && <Emoji id={bucket.emoji_id} />}
      <span className="font-medium">{bucket.name}</span>
      <span className="text-white/40">({bucket.track_ids.length})</span>

      {/* NEW: Linked playlist indicator */}
      {bucket.linked_playlist_name && (
        <span
          className="text-sm"
          style={{ color: bucketColor }}
        >
          ({bucket.linked_playlist_name})
        </span>
      )}
    </div>
  );
}
```

### Color extraction:
- If bucket has an emoji, derive color from emoji (may need emoji-to-color mapping)
- If no emoji, use a default accent color
- Consider using the same color logic used elsewhere for bucket styling

### Alternative: Use existing bucket color system
If buckets already have assigned colors (e.g., from position or emoji), reuse that:

```tsx
const bucketColor = useMemo(() => {
  // Existing bucket color logic
  return BUCKET_COLORS[bucket.position % BUCKET_COLORS.length];
}, [bucket.position]);
```

## Verification

1. Link a bucket to a playlist (via edit popup from task 06)
2. Verify the bucket header shows: `{emoji} {name} ({count}) (Linked Playlist Name)`
3. Verify the linked playlist name uses the bucket's color
4. Verify unlinked buckets don't show the extra parentheses
5. Test with various bucket colors/emojis to ensure readability
