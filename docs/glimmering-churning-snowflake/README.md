# Genre Selection & Settings Features

## Overview
Multi-genre support for music-minion-cli with two key features:
1. **Genre Selection Modal** - Click any genre tag to open multi-select with priority ordering
2. **Genre Settings Page** - Bulk rename/merge, emoji assignment, genre management

Primary genre (position=1) syncs to file metadata via database triggers for backward compatibility.

## Task Sequence
1. [01-database-migration-v41.md](./01-database-migration-v41.md) - Create genres/track_genres tables with sync triggers
2. [02-backend-queries-router.md](./02-backend-queries-router.md) - Genre API endpoints and query functions
3. [03-frontend-api-store.md](./03-frontend-api-store.md) - API client, Zustand store, Track type update
4. [04-genre-selection-modal.md](./04-genre-selection-modal.md) - GenreSelectionModal, GenreTag, TrackCard integration
5. [05-genre-settings-page.md](./05-genre-settings-page.md) - GenreSettingsSection, settings tab routing

## Success Criteria

### End-to-end verification:
```bash
cd ~/coding/music-minion-cli

# 1. Start the app
uv run music-minion --web

# 2. Database check
sqlite3 ~/.config/music-minion/music-minion.db ".schema genres"
sqlite3 ~/.config/music-minion/music-minion.db "SELECT * FROM genres LIMIT 5"

# 3. API check
curl http://localhost:8642/api/genres
```

### UI testing:
- Navigate to http://localhost:5173
- Click a genre tag on any track → modal opens
- Select multiple genres, verify numbered badges
- Save → track shows primary genre
- Settings → Genres tab → rename/merge/emoji works
- Delete blocked if tracks exist
- File metadata reflects primary genre (`mutagen-inspect file.mp3`)

## Dependencies
- SQLite 3.x (triggers supported)
- Radix UI Dialog (already installed)
- Zustand (already installed)
- Existing patterns: EmojiSettingsSection, SkippedTracksDialog, queries/emojis.py

## Key Decisions
- **Trigger-based sync**: SQLite triggers keep tracks.genre in sync with track_genres position=1
- **Genre normalization**: strip + lowercase + NFC Unicode (matches emoji pattern)
- **Merge behavior**: Tracks with both genres keep lowest position, delete duplicate
- **Delete protection**: Block delete if any tracks use the genre
- **Genre-emoji source_id**: Uses genre_id (integer) not genre name for stability
- **TrackCard display**: Primary genre only (secondary visible via emoji badges)
