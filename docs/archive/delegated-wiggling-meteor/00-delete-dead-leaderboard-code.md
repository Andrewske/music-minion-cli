---
task: 00-delete-dead-leaderboard-code
status: done
depends: []
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
  - path: src/music_minion/commands/rating.py
    action: modify
  - path: web/frontend/src/components/Leaderboard.tsx
    action: delete
  - path: web/frontend/src/types/index.ts
    action: modify
  - path: web/backend/schemas.py
    action: modify
---

# Delete Dead Leaderboard Code

## Context
The leaderboard/rankings feature is unused. The web UI component is never rendered, and we're removing the CLI command. Delete all related dead code.

## Files to Modify/Delete

### 1. Delete from `src/music_minion/domain/rating/database.py`:
- `get_playlist_leaderboard()` function (lines 48-97)
- `get_playlist_tracks_by_rating()` function (lines 466-511)

### 2. Delete from `src/music_minion/commands/rating.py`:
- Remove import: `get_playlist_leaderboard` (line 18)
- Delete `handle_rankings_command()` function (lines 460-530 approx)
- Remove from command registry if present

### 3. Delete file:
- `web/frontend/src/components/Leaderboard.tsx`

### 4. Delete from `web/frontend/src/types/index.ts`:
- `LeaderboardEntry` interface

### 5. Delete from `web/backend/schemas.py`:
- `LeaderboardEntry` class (line 74)

## Verification
```bash
# Ensure no remaining references
grep -r "leaderboard\|LeaderboardEntry\|get_playlist_tracks_by_rating" src/ web/ --include="*.py" --include="*.ts" --include="*.tsx"

# Run tests
uv run pytest src/music_minion/domain/rating/ -v
```
