# Add Emoji Tagging to Web Interface Pages

## Overview
Extend the emoji tagging feature (currently only on radio now-playing) to all other web pages where tracks are displayed. All locations will have interactive emoji support (add/remove via picker).

## Task Sequence
1. [01-trackcard-emoji-support.md](./01-trackcard-emoji-support.md) - Add emoji tagging to comparison TrackCard
2. [02-history-top-tracks-emoji.md](./02-history-top-tracks-emoji.md) - Add emoji tagging to History top tracks
3. [03-upnext-emoji-support.md](./03-upnext-emoji-support.md) - Add emoji tagging to UpNext queue
4. [04-history-timeline-emoji.md](./04-history-timeline-emoji.md) - Add emoji tagging to History timeline entries
5. [05-playlist-table-emoji.md](./05-playlist-table-emoji.md) - Add emoji column to PlaylistTracksTable

## Success Criteria
- Emoji badges render on all 5 locations
- Add/remove emoji works interactively everywhere
- Changes persist after page refresh
- Compact mode used appropriately in dense layouts (tables, lists)
- Full mode used on larger cards (TrackCard comparison)

## Dependencies
- Existing emoji infrastructure: `EmojiTrackActions`, `useTrackEmojis` hook
- API endpoints may need to include `emojis` field in track responses
- React Query for cache invalidation on emoji changes
