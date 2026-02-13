# Playlist Selection UI Implementation (TanStack Router)

## Overview

This plan implements a playlist selection UI with TanStack Router for type-safe, file-based routing. The implementation replaces the existing hash-based routing with a modern, type-safe routing system that integrates seamlessly with TanStack Query (already in use).

### What's Being Built
- **Playlist Selection Page** (`/playlist-builder`): Browse and create local manual playlists
- **Playlist Builder Route** (`/playlist-builder/$playlistId`): Dynamic route for building playlists
- **Clean URLs**: `/playlist-builder/123` instead of hash-based routing
- **Type-Safe Navigation**: Full TypeScript inference for route params

### Why TanStack Router
- Type-safe routing with automatic parameter inference
- File-based routing for better code organization
- Integrates with TanStack Query (already used in project)
- Built-in DevTools for debugging
- Automatic code splitting

## Task Sequence

1. [01-install-tanstack-router.md](./01-install-tanstack-router.md) - Install dependencies
2. [02-configure-vite-plugin.md](./02-configure-vite-plugin.md) - Configure Vite with router plugin
3. [03-backend-api-endpoint.md](./03-backend-api-endpoint.md) - Add POST /api/playlists endpoint
4. [04-frontend-types-and-api.md](./04-frontend-types-and-api.md) - Update TypeScript types and API client
5. [05-create-route-structure.md](./05-create-route-structure.md) - Create route directory and base routes
6. [06-playlist-selection-route.md](./06-playlist-selection-route.md) - Implement playlist selection UI
7. [07-playlist-builder-dynamic-route.md](./07-playlist-builder-dynamic-route.md) - Implement dynamic builder route
8. [08-update-app-and-playlist-builder.md](./08-update-app-and-playlist-builder.md) - Wire up router in App.tsx

## Success Criteria

### Functionality
- [ ] Can navigate to `/` and see ComparisonView
- [ ] Can navigate to `/playlist-builder` and see playlist selection page
- [ ] Can create new playlist and auto-navigate to builder (no flash of "not found")
- [ ] Can click existing playlist and navigate to builder
- [ ] Playlist URLs use numeric IDs (e.g., `/playlist-builder/123`)
- [ ] Back navigation returns to selection page
- [ ] Invalid playlist IDs show not-found page with back link
- [ ] Error state shows when playlist fetch fails with retry button

### Technical
- [ ] `routeTree.gen.ts` automatically generated on dev server start
- [ ] TypeScript compilation succeeds with no errors
- [ ] All routes type-safe with parameter autocomplete
- [ ] DevTools panel appears in bottom-right corner (dev mode only)
- [ ] Browser back/forward buttons work correctly
- [ ] Network tab shows separate chunk loads for routes (code splitting works)

### Backend
- [ ] POST `/api/playlists` endpoint creates playlists
- [ ] Returns 400 for duplicate names
- [ ] Returns created playlist with all fields

## Execution Instructions

1. **Execute tasks in numerical order** (01 → 08)
2. Each task file contains:
   - Files to modify/create
   - Implementation details with code snippets
   - Acceptance criteria
   - Dependencies on previous tasks
3. **Verify acceptance criteria** before moving to next task
4. Start dev server after task 02 to enable auto-generation

### Running the Application
```bash
# Terminal 1: Start full stack
uv run music-minion --web

# Or separate terminals:
# Backend
uv run uvicorn web.backend.main:app --reload

# Frontend
cd web/frontend
npm run dev
```

## Dependencies

### External Packages (Task 01)
- `@tanstack/react-router` - Router library
- `@tanstack/react-router-devtools` - Dev tools
- `@tanstack/router-plugin` - Vite plugin

### Existing Components/Hooks
- `ComparisonView` component (`src/components/ComparisonView`)
- `PlaylistBuilder` component (`src/pages/PlaylistBuilder`)
- `usePlaylists` hook (`src/hooks/usePlaylists`)
- `useBuilderSession` hook (`src/hooks/useBuilderSession`)

### Backend
- `create_playlist()` function in `music_minion.domain.playlists.crud`
- SQLite database with playlists table

## Verification Steps

### After Task 03 (Backend)
```bash
# Test create endpoint
curl -X POST http://localhost:8642/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Playlist", "description": "Testing"}'

# Test duplicate name (should return 400)
curl -X POST http://localhost:8642/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Playlist", "description": "Duplicate"}'
```

### After Task 08 (Frontend Complete)
1. Navigate to http://localhost:5173/
2. Navigate to http://localhost:5173/playlist-builder
3. Create a new playlist
4. Select an existing playlist
5. Test back navigation
6. Test invalid playlist name URL

## Edge Cases to Test
- Playlist names with special characters during creation (backend validation)
- Very long playlist names
- Empty playlist list (should show "no playlists" message)
- Network errors during creation (should show error message with retry)
- Network errors during playlist fetch (should show error with retry)
- Invalid playlist ID in URL (should show not-found page)
- Non-numeric playlist ID in URL (should show not-found page)

## Rollback Plan

If TanStack Router causes issues:

1. Uninstall packages:
   ```bash
   npm uninstall @tanstack/react-router @tanstack/react-router-devtools @tanstack/router-plugin
   ```
2. Revert `vite.config.ts` to original
3. Restore original `App.tsx` with hash routing
4. Delete `routes/` directory and `routeTree.gen.ts`
5. Backend changes are safe to keep (unused endpoints don't cause issues)

## Future Enhancements
- Add route loaders for prefetching playlist data
- Implement route-level error boundaries
- Add search params for filtering/sorting playlists
- Add route transitions/animations
- Implement route guards for session validation
- Add breadcrumb navigation
