---
task: 01-trackcard-emoji-support
depends: []
files:
  - path: web/frontend/src/components/TrackCard.tsx
    action: modify
---

# Add Emoji Tagging to TrackCard

## Context
TrackCard is used in the comparison view for A/B ranking. Adding emoji support here provides high visibility during ranking sessions and allows users to tag tracks as they evaluate them.

## Files to Modify/Create
- web/frontend/src/components/TrackCard.tsx (modify)

## Implementation Details
Add `EmojiTrackActions` component below the rating badge in the stats section.

**Location:** After line 104 (the stats/badges section)

```tsx
// After rating badge, new section
<EmojiTrackActions track={track} onUpdate={onTrackUpdate} />
```

**Props to add:**
- `onTrackUpdate?: (track: TrackInfo) => void` - callback for emoji changes

**Notes:**
- TrackInfo already has emojis field, no API changes needed
- Use full (non-compact) display since cards are large

## Verification
1. Navigate to `/comparison`
2. Verify emoji badges render below rating on track cards
3. Click "+" to add emoji, confirm it persists
4. Remove emoji, confirm removal
