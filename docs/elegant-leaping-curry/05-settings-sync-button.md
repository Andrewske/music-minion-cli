---
task: 05-settings-sync-button
status: pending
depends:
  - 03-backend-soundcloud-sync
  - 04-frontend-library-switcher
files:
  - path: web/frontend/src/components/Settings/SoundCloudImportSection.tsx
    action: modify
  - path: web/frontend/src/api/soundcloud.ts
    action: modify
---

# Settings: SoundCloud Sync Button

## Context

Add a "Sync Library" section to the SoundCloud settings tab that triggers the backend sync endpoint. Shows last sync time and handles auth expiry with toast notification.

## Files to Modify/Create

- `web/frontend/src/components/Settings/SoundCloudImportSection.tsx` (modify)
- `web/frontend/src/api/soundcloud.ts` (modify - add sync function)

## Implementation Details

### soundcloud.ts (add sync functions)

```typescript
export interface SyncResponse {
  tracks_synced: number;
  playlists_synced: number;
  likes_synced: number;
  errors: string[];
  last_synced_at: string;  // ISO timestamp
}

export interface SyncStatus {
  last_synced_at: string | null;
  track_count: number;
}

export async function getSoundCloudSyncStatus(): Promise<SyncStatus> {
  const response = await fetch('/api/soundcloud/sync/status');
  if (!response.ok) {
    throw new Error('Failed to get sync status');
  }
  return response.json();
}

export async function syncSoundCloudLibrary(): Promise<SyncResponse> {
  const response = await fetch('/api/soundcloud/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (response.status === 401) {
    // Auth expired - throw specific error for toast handling
    throw new Error('SOUNDCLOUD_AUTH_EXPIRED');
  }

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Sync failed');
  }

  return response.json();
}
```

### SoundCloudImportSection.tsx (add sync section)

Add at the top of the component, before the import wizard:

```typescript
import { useState, useEffect } from 'react';
import { toast } from 'sonner';  // or your toast library
import { syncSoundCloudLibrary, getSoundCloudSyncStatus, type SyncStatus } from '../../api/soundcloud';

// Inside the component, add state:
const [isSyncing, setIsSyncing] = useState(false);
const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
const [syncResult, setSyncResult] = useState<{ tracks: number; playlists: number; likes: number } | null>(null);

// Fetch sync status on mount
useEffect(() => {
  getSoundCloudSyncStatus()
    .then(setSyncStatus)
    .catch(() => {}); // Ignore errors
}, []);

const handleSync = async () => {
  setIsSyncing(true);
  setSyncResult(null);

  try {
    const result = await syncSoundCloudLibrary();
    setSyncResult({
      tracks: result.tracks_synced,
      playlists: result.playlists_synced,
      likes: result.likes_synced,
    });
    setSyncStatus({ last_synced_at: result.last_synced_at, track_count: result.tracks_synced });

    if (result.errors.length > 0) {
      toast.warning(`Sync completed with ${result.errors.length} errors`);
    } else {
      toast.success(`Synced ${result.tracks_synced} tracks`);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Sync failed';

    // Handle auth expiry with specific toast
    if (message === 'SOUNDCLOUD_AUTH_EXPIRED') {
      toast.error('SoundCloud session expired', {
        description: 'Re-authenticate in Settings > SoundCloud',
        action: {
          label: 'Re-auth',
          onClick: () => {/* Navigate to auth or trigger re-auth */},
        },
      });
    } else {
      toast.error(message);
    }
  } finally {
    setIsSyncing(false);
  }
};

// Format relative time
const formatLastSync = (iso: string) => {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};

// In the JSX, add before the existing import wizard section:
<div className="p-6 bg-slate-800 border border-slate-700 rounded-lg mb-6">
  <h3 className="text-lg font-semibold text-white mb-2">Sync SoundCloud Library</h3>
  <p className="text-sm text-slate-400 mb-4">
    Import your SoundCloud likes and playlists for streaming in the app.
    This creates separate records that can be browsed in the SoundCloud library view.
  </p>

  <div className="flex items-center gap-4">
    <button
      onClick={handleSync}
      disabled={isSyncing}
      className="px-6 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
    >
      {isSyncing ? 'Syncing...' : 'Sync Now'}
    </button>

    {syncStatus?.last_synced_at && (
      <span className="text-sm text-slate-400">
        Last synced: {formatLastSync(syncStatus.last_synced_at)}
        {' • '}
        {syncStatus.track_count} tracks
      </span>
    )}
  </div>

  {syncResult && (
    <p className="mt-3 text-sm text-green-400">
      Synced {syncResult.tracks} tracks, {syncResult.playlists} playlists, {syncResult.likes} likes
    </p>
  )}
</div>
```

### Backend: Add sync status endpoint

Add to `web/backend/routers/soundcloud.py`:

```python
@router.get("/soundcloud/sync/status")
async def get_sync_status(db=Depends(get_db)):
    """Get last sync timestamp and track count."""
    cursor = db.execute("""
        SELECT
            MAX(created_at) as last_synced_at,
            COUNT(*) as track_count
        FROM tracks WHERE source = 'soundcloud'
    """)
    row = cursor.fetchone()
    return {
        "last_synced_at": row["last_synced_at"],
        "track_count": row["track_count"] or 0,
    }
```

## Verification

1. Go to Settings > SoundCloud tab
2. Click "Sync Now" button
3. Verify loading state shows
4. On success, verify counts displayed
5. Switch to SoundCloud library in sidebar - should see synced playlists
6. Play a track - should stream from SoundCloud
