---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration v39 - Quick Tag Tables

## Context
Foundation for the Quick Tag feature. Creates the schema for storing dimension pairs (the emoji comparisons) and user votes on tracks. Must be completed before backend API can function.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

### 1. Bump Schema Version
Change `SCHEMA_VERSION = 38` to `SCHEMA_VERSION = 39`

### 2. Add Migration Block
Add migration for v39 in `migrate_database()` function:

```sql
-- Static reference table for dimension pairs
CREATE TABLE IF NOT EXISTS dimension_pairs (
    id TEXT PRIMARY KEY,
    left_emoji TEXT NOT NULL,
    right_emoji TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL
);

-- Votes table (single vote per track-dimension, upsert overwrites)
CREATE TABLE IF NOT EXISTS track_dimension_votes (
    track_id INTEGER NOT NULL,
    dimension_id TEXT NOT NULL,
    vote INTEGER NOT NULL CHECK (vote IN (-1, 0, 1)),
    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (track_id, dimension_id),
    FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
    FOREIGN KEY (dimension_id) REFERENCES dimension_pairs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dim_votes_track ON track_dimension_votes (track_id);
```

### 3. Seed Dimension Pairs
Insert the 10 bass music dimensions:

| id | left_emoji | right_emoji | label | description | sort_order |
|----|------------|-------------|-------|-------------|------------|
| filth | ✨ | 💀 | Pristine vs Filthy | Grimy sound design vs clean production | 1 |
| energy | 🐢 | 🚀 | Cruisin' vs Raging | Chill vs peak-time banger | 2 |
| drop | 🪶 | 💣 | Subtle vs Devastating | Smooth transitions vs face-melting drops | 3 |
| groove | 🤖 | 💃 | Mechanical vs Groovy | Robotic/stiff vs infectious bounce | 4 |
| depth | ☀️ | 🌊 | Bright vs Deep | High/airy vs sub-heavy darkness | 5 |
| weirdness | 🏠 | 👽 | Familiar vs Alien | Conventional vs mind-bending | 6 |
| headbang | 😴 | 🤘 | Nodding vs Necking | Head nod vs full neck workout | 7 |
| vocals | 🎸 | 🎤 | Instrumental vs Vocal | Purely instrumental vs vocal-driven | 8 |
| buildup | ⚡ | 🌀 | Quick vs Epic | Instant drops vs cinematic tension | 9 |
| dancefloor | 🎧 | 🪩 | Headphones vs Dancefloor | Bedroom listening vs club weapon | 10 |

## Verification
1. Run the app to trigger migration: `uv run music-minion --help`
2. Check tables exist:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db ".schema dimension_pairs"
   sqlite3 ~/.local/share/music-minion/music_minion.db ".schema track_dimension_votes"
   ```
3. Verify seed data:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT id, label FROM dimension_pairs ORDER BY sort_order"
   ```
