# Playlist Pinning

## Overview
Pin playlists to the top of the sidebar with drag-to-reorder support. Adds a `pin_order` column to the database, CRUD functions, REST API endpoints, and React UI with @dnd-kit for drag-and-drop reordering.

## Task Sequence
1. [01-database-migration.md](./01-database-migration.md) - Add pin_order column (v32 migration)
2. [02-crud-functions.md](./02-crud-functions.md) - Add pin/unpin/reorder CRUD functions
3. [03-backend-api.md](./03-backend-api.md) - Add REST API endpoints for pinning
4. [04-frontend-types-api.md](./04-frontend-types-api.md) - Update TypeScript types and API functions
5. [05-sidebar-ui.md](./05-sidebar-ui.md) - Add pin/unpin UI to sidebar
6. [06-drag-reorder.md](./06-drag-reorder.md) - Add drag-to-reorder for pinned playlists

## Success Criteria
1. Start the app: `uv run music-minion --web`
2. Check migration: Verify "Migrating to v32" message appears (first run only)
3. Test pinning: Hover over a playlist, click pin icon, verify it moves to top with pin icon
4. Test unpinning: Hover over pinned playlist, click pin icon, verify it returns to alphabetical position
5. Test reorder: Drag a pinned playlist above/below another pinned playlist, verify order persists after refresh
6. Test persistence: Refresh browser, verify pinned playlists remain pinned in correct order

## Dependencies
- SQLite (existing)
- FastAPI (existing)
- React + @tanstack/react-query (existing)
- @dnd-kit/core, @dnd-kit/sortable (existing - verify in package.json)
- Lucide React icons (existing)
