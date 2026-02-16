---
task: 04-frontend-types-api
status: done
depends: [03-backend-api]
files:
  - path: web/frontend/src/types/index.ts
    action: modify
  - path: web/frontend/src/api/playlists.ts
    action: modify
---

# Frontend Type + API

## Context
Update TypeScript types and add API functions to call the new pin endpoints. This provides the interface layer between React components and the backend.

## Files to Modify/Create
- web/frontend/src/types/index.ts (modify)
- web/frontend/src/api/playlists.ts (modify)

## Implementation Details

**Step 1: Update Playlist interface**

Add to Playlist interface in `types/index.ts`:
```typescript
pin_order: number | null;
```

**Step 2: Add API functions to `playlists.ts`**

```typescript
export async function pinPlaylist(playlistId: number): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to pin playlist');
  return response.json();
}

export async function unpinPlaylist(playlistId: number): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to unpin playlist');
  return response.json();
}

export async function reorderPinnedPlaylist(
  playlistId: number,
  position: number
): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ position }),
  });
  if (!response.ok) throw new Error('Failed to reorder playlist');
  return response.json();
}
```

**Step 3: Commit**

```bash
git add web/frontend/src/types/index.ts web/frontend/src/api/playlists.ts
git commit -m "feat: add playlist pinning types and API functions"
```

## Verification

Run TypeScript check:
```bash
cd web/frontend && npx tsc --noEmit
```
Expected: No type errors
