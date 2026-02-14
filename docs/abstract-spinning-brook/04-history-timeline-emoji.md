---
task: 04-history-timeline-emoji
status: done
depends: [02-history-top-tracks-emoji]
files:
  - path: web/frontend/src/components/HistoryPage.tsx
    action: modify
---

# Add Emoji Tagging to History Timeline

## Context
History timeline shows individual play history entries. Adding emoji support completes the history page integration.

## Files to Modify/Create
- web/frontend/src/components/HistoryPage.tsx (modify)

## Implementation Details

**Location:** Lines 309-328, inside the timeline entry map

Add compact `EmojiTrackActions` after title/artist:

```tsx
// Inside timeline entry, after title/artist block
<EmojiTrackActions track={entry.track} onUpdate={handleUpdate} compact />
```

**Positioning options:**
1. Inline with timestamp (right side)
2. Below artist (new row)

**State management:**
- Reuse the same update pattern from task 02
- May need to update entry in the infinite query cache

**Notes:**
- Depends on task 02 which may have already verified API returns emojis
- Uses same update handler pattern

## Verification
1. Navigate to `/history`
2. Scroll through timeline entries
3. Verify emoji badges appear on history items
4. Add/remove emojis and confirm persistence
