---
task: 03-frontend-stats-modal
status: done
depends: [02-backend-schema-endpoint]
files:
  - path: web/frontend/src/types/index.ts
    action: modify
  - path: web/frontend/src/components/StatsModal.tsx
    action: modify
---

# Update Frontend StatsModal for Unified Playlist Stats

## Context
Remove the global stats code path from StatsModal. Add daily pace stat card and estimated days to playlist stats. Keep existing Top Genres + Top Artists layout (PlaylistTracksTable already serves as the leaderboard).

## Files to Modify/Create
- `web/frontend/src/types/index.ts` (modify)
- `web/frontend/src/components/StatsModal.tsx` (modify)

## Implementation Details

### 1. Update `PlaylistStatsResponse` type in types/index.ts

Add new fields to the existing interface:
```typescript
export interface PlaylistStatsResponse {
  // ... existing fields ...
  // NEW FIELDS:
  avg_comparisons_per_day: number;
  estimated_days_to_full_coverage: number | null;
}
```

### 2. Refactor StatsModal.tsx

**Remove (global stats code path):**
- `import { useStats } from '../hooks/useStats';` - the useStats import
- `const { data: globalStats, ... } = useStats();` - the useStats hook call
- `const isPlaylistMode = !!playlistId;` - the mode conditional
- The globalStats StatCard rendering branch (the `globalStats ?` conditional in stat cards)
- The globalStats GenreChart rendering (the `globalStats ?` conditional in charts)
- The globalStats Leaderboard rendering (the `globalStats ?` conditional)
- The global-only "Additional Stats" section with estimated_days_to_coverage
- Remove `Leaderboard` import if no longer used

**Add to playlist stat cards:**
```tsx
<StatCard
  icon="📈"
  value={playlistStats.avg_comparisons_per_day.toFixed(1)}
  label="Daily Pace"
  subtitle="Comparisons per day"
/>
```

**Add estimated days section (after charts, before PlaylistTracksTable):**
```tsx
{playlistStats.estimated_days_to_full_coverage && (
  <div className="mt-6 text-center">
    <p className="text-slate-400">
      Estimated {Math.round(playlistStats.estimated_days_to_full_coverage)} days to full coverage at current pace
    </p>
  </div>
)}
```

**Simplify logic:**
- Remove `isPlaylistMode` conditional - always use playlist stats
- `playlistId` prop becomes required (no null case)
- Simplify loading/error conditionals to only use playlistStats

## Verification
1. Run `uv run music-minion --web`
2. Open http://localhost:5173
3. Go to comparison view, select any playlist
4. Click stats button
5. Verify: daily pace stat card shows, estimated days shows (if applicable)
6. Test with "All" playlist - should show library-wide stats
