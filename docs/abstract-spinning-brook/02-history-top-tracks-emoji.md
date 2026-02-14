---
task: 02-history-top-tracks-emoji
depends: []
files:
  - path: web/frontend/src/components/HistoryPage.tsx
    action: modify
  - path: web/backend/routers/radio.py
    action: modify
---

# Add Emoji Tagging to History Top Tracks

## Context
Top Tracks section shows most-played tracks. Adding emoji tagging here lets users tag their frequently played music for organization.

## Files to Modify/Create
- web/frontend/src/components/HistoryPage.tsx (modify)
- web/backend/routers/radio.py (modify) - may need to include emojis in response

## Implementation Details

### Frontend (HistoryPage.tsx)
**Location:** Lines 259-279, inside the top tracks map

Add compact `EmojiTrackActions` after the play count span:

```tsx
// After play count span (line 275-276)
<EmojiTrackActions track={trackStat.track} onUpdate={handleUpdate} compact />
```

**State management:**
- Need local state or React Query mutation to handle track updates
- On emoji add/remove, update the track in the topTracks array

### Backend (if needed)
Check `/api/radio/top-tracks` endpoint - ensure it returns `emojis` field for each track.

## Verification
1. Navigate to `/history`
2. Select a station to view top tracks
3. Verify emoji badges appear next to play count
4. Add/remove emojis and confirm persistence
