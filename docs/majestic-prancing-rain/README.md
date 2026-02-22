# Quick Tag Feature - Emoji Dimension Voting

## Overview
Persistent sidebar component for quick-tagging tracks with emoji pairs representing bass music dimensions. Users vote on the currently playing track with one click, building up dimensional profiles over time.

**10 Bass Music Dimensions:**
- ✨/💀 Filth - ☀️/🌊 Depth - 🐢/🚀 Energy - 🏠/👽 Weirdness
- 🪶/💣 Drop - 😴/🤘 Headbang - 🤖/💃 Groove - 🎸/🎤 Vocals
- ⚡/🌀 Buildup - 🎧/🪩 Dancefloor

## Task Sequence
1. [01-database-migration.md](./01-database-migration.md) - Schema v39: dimension_pairs + track_dimension_votes tables
2. [02-backend-api.md](./02-backend-api.md) - FastAPI router: GET dimensions, POST vote, GET summary
3. [03-frontend-state.md](./03-frontend-state.md) - TypeScript types + Zustand store for dimension cycling
4. [04-sidebar-component.md](./04-sidebar-component.md) - SidebarQuickTag UI component + root layout integration

## Success Criteria
1. Start app: `music-minion --web`
2. Play any track
3. Quick Tag section visible in sidebar with emoji pair
4. Click emoji → vote recorded, advances to next dimension
5. Navigate dimensions with arrows
6. Change track → dimension persists, can vote on new track
7. Verify in database: `sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM track_dimension_votes"`

## Dependencies
- Existing: SidebarSection component, playerStore (currentTrack), FastAPI backend
- No external packages required
