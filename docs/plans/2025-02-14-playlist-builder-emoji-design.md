# Playlist Builder Emoji Integration

## Overview

Add emoji tagging to the web PlaylistBuilder for tag-while-browsing and filter-by-emoji workflows.

## Requirements

1. **Tag while browsing**: Add/remove emojis on the currently displayed track
2. **Filter by emoji**: Filter candidates to show only tracks with specific emojis

## Design

### TrackDisplay Changes

Add `EmojiReactions` component inline with existing metadata badges:

```
[Genre] [2024] [128 BPM] [Key] [🔥] [⚡] [+ Add]
```

- Reuse existing `EmojiReactions` component (non-compact mode with "+ Add" button)
- Reuse existing `EmojiPicker` modal (emoji-mart)
- Wire to existing track emoji APIs

### FilterEditor Changes

Add "emoji" as a filter field:

- Field: `emoji`
- Operator: `has` (track has this emoji)
- Value: Emoji picker or dropdown of frequently used emojis

### API Endpoints (existing)

- `POST /api/tracks/{id}/emojis` - add emoji to track
- `DELETE /api/tracks/{id}/emojis/{emojiId}` - remove emoji from track
- `GET /api/tracks/{id}/emojis` - get track's emojis
- Filter param: `?emoji=🔥` on candidates endpoint

### State Management

- Track emojis fetched with track data (add to `Track` type if not present)
- Mutations invalidate track query to refresh UI
- Filter state already managed by `useBuilderSession` hook

## Files to Modify

1. `web/frontend/src/pages/PlaylistBuilder.tsx` - Add emoji state and picker to TrackDisplay
2. `web/frontend/src/components/builder/FilterEditor.tsx` - Add emoji field option
3. `web/frontend/src/api/builder.ts` - Add emoji filter param to getCandidates
4. `src/music_minion/api/routes/builder.py` - Handle emoji filter in candidates query (if not already)

## Out of Scope

- Emoji column in TrackQueueTable (keep table clean)
- Batch emoji tagging (tag multiple tracks at once)
- Custom emoji upload in builder context
