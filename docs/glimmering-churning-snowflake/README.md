# Genre Selection & Settings Features

## Overview

Two features for music-minion-cli web frontend:
1. **Genre Selection Modal** - Click any genre tag to open multi-select modal with priority ordering
2. **Genre Settings Page** - Mass rename/merge genres, assign emojis to genres

**Key Design Decisions:**
- New normalized `genres` and `track_genres` tables (not comma-separated)
- Primary genre (position=1) written to file metadata, all genres in DB
- Genre emojis use existing `track_emojis` system with `source_type='genre'`

## Task Sequence

| # | Task | Description | Depends On |
|---|------|-------------|------------|
| 1 | [01-database-migration.md](./01-database-migration.md) | Schema v41 with genres/track_genres tables | - |
| 2 | [02-genres-api-router.md](./02-genres-api-router.md) | FastAPI endpoints for genre CRUD | 01 |
| 3 | [03-frontend-api-state.md](./03-frontend-api-state.md) | TypeScript API client + Zustand store | 02 |
| 4 | [04-genre-selection-modal.md](./04-genre-selection-modal.md) | Modal + ClickableGenre + TrackCard update | 03 |
| 5 | [05-genre-settings-page.md](./05-genre-settings-page.md) | Settings tab with rename/merge/emoji | 03 |

**Parallelization:** Tasks 04 and 05 can run in parallel after 03 completes.

## Success Criteria

End-to-end verification:

1. **Database migration works:**
   ```bash
   uv run music-minion  # Auto-migrates to v41
   sqlite3 ~/.config/music-minion/music-minion.db "SELECT name, COUNT(*) as tracks FROM genres g JOIN track_genres tg ON g.id = tg.genre_id GROUP BY g.id ORDER BY tracks DESC LIMIT 5"
   ```

2. **Genre selection works:**
   - Click genre on any track → modal opens
   - Select multiple genres with numbered badges
   - Save → primary genre shows on track card
   - File metadata updated for local tracks

3. **Settings page works:**
   - Navigate to /settings?tab=genres
   - Rename genre → all tracks updated
   - Rename to existing name → merge confirmation → tracks combined
   - Assign emoji → emoji appears on all tracks with that genre

4. **Emoji propagation works:**
   - Assign emoji to genre in settings
   - All tracks with that genre show the emoji
   - Change track's genre → emoji updates accordingly

## Dependencies

- Existing `track_emojis` table with `source_type`/`source_id` columns (v40)
- Radix UI Dialog pattern (`SkippedTracksDialog.tsx`)
- Settings page pattern (`EmojiSettingsSection.tsx`)
- Zustand state management
- EmojiPicker component

## Files Modified

| File | Action | Task |
|------|--------|------|
| `src/music_minion/core/database.py` | modify | 01 |
| `web/backend/routers/genres.py` | create | 02 |
| `web/backend/main.py` | modify | 02 |
| `web/frontend/src/api/genres.ts` | create | 03 |
| `web/frontend/src/stores/genreStore.ts` | create | 03 |
| `web/frontend/src/types/index.ts` | modify | 03 |
| `web/frontend/src/components/GenreSelectionModal.tsx` | create | 04 |
| `web/frontend/src/components/ClickableGenre.tsx` | create | 04 |
| `web/frontend/src/components/TrackCard.tsx` | modify | 04 |
| `web/frontend/src/components/Settings/GenreSettingsSection.tsx` | create | 05 |
| `web/frontend/src/components/Settings/SettingsPage.tsx` | modify | 05 |
| `web/frontend/src/routes/settings.tsx` | modify | 05 |
