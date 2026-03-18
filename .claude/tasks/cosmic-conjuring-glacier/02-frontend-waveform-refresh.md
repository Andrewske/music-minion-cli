---
task: 02-frontend-waveform-refresh
status: done
depends: [01-backend-waveform-endpoints]
files:
  - path: web/frontend/src/api/tracks.ts
    action: modify
  - path: web/frontend/src/hooks/useWavesurfer.ts
    action: modify
  - path: web/frontend/src/components/WaveformPlayer.tsx
    action: modify
  - path: web/frontend/src/components/Settings/SoundCloudImportSection.tsx
    action: modify
---

# Frontend: Waveform Refresh (API + Hook + UI)

## Context
The frontend needs API functions for cache invalidation, a `refreshWaveform` callback in `useWavesurfer`, a refresh button on `WaveformPlayer`, and a bulk purge button in SoundCloud settings.

## Files to Modify
- `web/frontend/src/api/tracks.ts` — new API functions
- `web/frontend/src/hooks/useWavesurfer.ts` — refresh callback + `isRefreshing` state
- `web/frontend/src/components/WaveformPlayer.tsx` — refresh button
- `web/frontend/src/components/Settings/SoundCloudImportSection.tsx` — bulk purge button

## Implementation Details

### tracks.ts — New API functions

```typescript
export async function refreshWaveform(trackId: number): Promise<WaveformData> {
  // 1. Delete backend cache
  await fetch(`/api/tracks/${trackId}/waveform`, { method: 'DELETE' });
  // 2. Evict from in-memory cache
  waveformCache.delete(trackId);
  // 3. Re-fetch fresh data
  return getWaveformData(trackId);
}

export async function purgeSoundcloudWaveforms(): Promise<{ purged: number }> {
  const response = await fetch('/api/waveforms/purge-soundcloud', { method: 'POST' });
  if (!response.ok) throw new Error(`Purge failed: ${response.statusText}`);
  // Clear entire in-memory cache since we don't know which were SC
  waveformCache.clear();
  return response.json();
}
```

**Critical:** Must evict from `waveformCache` Map (line 4 of tracks.ts) — otherwise the stale Promise is returned even after backend cache is deleted.

### useWavesurfer.ts — refreshWaveform callback + isRefreshing state

Add a `refreshWaveform` function and `isRefreshing` boolean to the hook's return value.

**Add static import at top of file:**
```typescript
import { refreshWaveform as apiRefreshWaveform } from '../api/tracks';
```

**Add state and callback:**
```typescript
const [isRefreshing, setIsRefreshing] = useState(false);

const refreshWaveformData = useCallback(async (): Promise<void> => {
  setIsRefreshing(true);
  try {
    // Pause playback before destroying to avoid abrupt cutoff
    wavesurferRef.current?.pause();
    await apiRefreshWaveform(trackId);
    // Re-init wavesurfer with fresh data (user hits play when ready)
    retryLoad();
  } catch (err) {
    // Surface auth/network errors — user sees toast, not silent failure
    throw err;
  } finally {
    setIsRefreshing(false);
  }
}, [trackId, retryLoad]);
```

**Return from hook:**
```typescript
return {
  containerRef,
  currentTime,
  duration,
  error,
  isRefreshing,
  refreshWaveform: refreshWaveformData,
  retryLoad,
  seekToPercent,
  seekRelative,
  togglePlayPause,
};
```

### WaveformPlayer.tsx — Refresh button

Add a refresh icon button near the time display. Uses `isRefreshing` to show spinner and prevent double-clicks.

```tsx
<button
  onClick={async () => {
    try {
      await refreshWaveform();
    } catch {
      toast.error('Failed to refresh waveform — check SoundCloud auth in Settings');
    }
  }}
  disabled={isRefreshing}
  className="w-6 h-6 flex items-center justify-center text-white/20 hover:text-white/60 transition-colors disabled:opacity-30"
  aria-label="Refresh waveform"
  title="Refresh waveform"
>
  {isRefreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
</button>
```

**Error handling:** On SC OAuth expiry or network failure, the catch block shows a toast directing the user to Settings to re-authenticate. This prevents the case where cache is deleted but re-fetch fails, leaving no waveform.

### Bulk purge — SoundCloud settings tab

Add to `web/frontend/src/components/Settings/SoundCloudImportSection.tsx`:
- "Purge SoundCloud Waveforms" button with destructive styling
- **Confirmation dialog** (AlertDialog) before executing — "Purge all cached SoundCloud waveforms? They'll re-download on next view."
- Calls `purgeSoundcloudWaveforms()` from `api/tracks.ts`
- Shows toast with count: "Purged N SoundCloud waveforms"
- Brief description text: "Re-downloads all SoundCloud waveforms on next view"

## Verification
1. Open a track with a bad waveform → click refresh → spinner shows → waveform reloads with new data
2. Click refresh during playback → audio pauses, waveform refreshes (no abrupt cutoff)
3. Disconnect network → click refresh → toast shows error message
4. Settings → SoundCloud → click "Purge SoundCloud Waveforms" → confirmation dialog → confirm → toast shows "Purged N waveforms"
5. Visit a purged track → waveform lazy-loads fresh from SoundCloud
