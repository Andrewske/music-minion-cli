---
task: 06-bucket-edit-popup
status: done
depends: [05-frontend-hook]
files:
  - path: web/frontend/src/components/organizer/BucketEditPopup.tsx
    action: modify
  - path: web/frontend/src/api/playlists.ts
    action: modify
---

# UI: Bucket Edit Dialog + Header Indicator

## Context
Extends the existing `BucketEditDialog` to include a playlist selector for linking buckets to playlists, and adds visual indicator in bucket headers showing linked playlist name.

**Note:** This task combines original tasks 06 (edit dialog) and 07 (header indicator).

## Files to Modify/Create
- web/frontend/src/components/organizer/BucketEditDialog.tsx (modify)
- web/frontend/src/components/organizer/BucketList.tsx (modify - header indicator)
- web/frontend/src/api/playlists.ts (modify - add playlist listing by library)

## Implementation Details

### Playlist selector requirements:
- Filter: Same library as parent playlist, exclude parent playlist
- Shows current link status (linked playlist name if linked)
- Combobox/select component with search
- "Not linked" option to unlink

### Component structure:

```tsx
interface BucketEditPopupProps {
  bucket: Bucket;
  parentPlaylistId: number;
  parentLibrary: string;
  onUpdate: (updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onLink: (playlistId: number | null) => Promise<void>;
  onClose: () => void;
}

function BucketEditPopup({ bucket, parentPlaylistId, parentLibrary, onUpdate, onLink, onClose }: BucketEditPopupProps) {
  // Fetch playlists for selector
  const { data: playlists } = useQuery({
    queryKey: ['playlists', parentLibrary],
    queryFn: () => getPlaylistsByLibrary(parentLibrary),
  });

  // Filter: same library, exclude parent
  const availablePlaylists = playlists?.filter(p =>
    p.id !== parentPlaylistId && p.library === parentLibrary
  ) ?? [];

  // State for name, emoji (existing)
  // State for selected playlist ID

  return (
    <Dialog>
      {/* Existing: Name input */}
      {/* Existing: Emoji picker */}

      {/* NEW: Playlist link selector */}
      <div>
        <Label>Link to Playlist</Label>
        <Select value={selectedPlaylistId} onValueChange={handlePlaylistChange}>
          <SelectTrigger>
            <SelectValue placeholder="Not linked" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="unlink">Not linked</SelectItem>
            {availablePlaylists.map(p => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Save/Cancel buttons */}
    </Dialog>
  );
}
```

### Bucket header indicator:

Add visual indicator in bucket headers for linked buckets:

```tsx
function BucketHeader({ bucket, ... }: BucketHeaderProps) {
  return (
    <div className="flex items-center gap-2">
      {bucket.emoji_id && <Emoji id={bucket.emoji_id} />}
      <span className="font-medium">{bucket.name}</span>
      <span className="text-white/40">({bucket.track_ids.length})</span>

      {/* Linked playlist indicator */}
      {bucket.linked_playlist_name && (
        <>
          <span className="text-white/30">🔗</span>
          <span className="text-sm text-white/50">
            {bucket.linked_playlist_name}
          </span>
        </>
      )}
    </div>
  );
}
```

The chain-link icon (🔗) provides at-a-glance visibility of linked status even in compact views.

### Add to playlists API:

```typescript
export async function getPlaylistsByLibrary(library: string): Promise<Playlist[]> {
  const response = await fetch(`${API_BASE}/playlists?library=${encodeURIComponent(library)}`);
  if (!response.ok) {
    throw new Error('Failed to fetch playlists');
  }
  return response.json();
}
```

**Backend requirement:** Ensure `/api/playlists` supports `?library=` query parameter filtering.

## Verification

1. Open playlist organizer, click edit on a bucket
2. Verify playlist selector shows:
   - "+ Create new playlist" at top
   - "Not linked" option
   - Playlists from same library (not the parent playlist)
3. Link bucket to existing playlist → verify bucket shows linked indicator
4. Create new playlist from bucket → verify new playlist created and linked
5. Unlink bucket → verify "Not linked" state
