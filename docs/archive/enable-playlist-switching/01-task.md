## Files to Modify/Create

- web/frontend/src/components/ComparisonView.tsx
- web/frontend/src/components/SessionProgress.tsx

## Implementation Details

Enable playlist switching during active comparison sessions by modifying the playlist change handler to start a new session instead of resetting the current one.

### Changes Made:

1. **ComparisonView.tsx**: Modified `handlePlaylistChange` to start a new session with the selected playlist instead of calling `reset()`
2. **SessionProgress.tsx**: No changes needed - playlist dropdown was already enabled during active sessions
3. **State Management**: Preserved priority folder setting when starting new session
4. **Data Preservation**: Current session data remains intact as new session replaces it cleanly

### Technical Approach:

- Updated playlist change handler to call `startSession.mutate()` with selected playlist and preserved priority folder
- Removed unused `reset` import from comparison store
- Ensured type safety and followed FP principles from CLAUDE.md

## Acceptance Criteria

- [x] Users can change playlists during active comparison sessions
- [x] New session starts with selected playlist
- [x] Current session data is preserved (not lost/reset)
- [x] Settings like priority folder are maintained in new session
- [x] Playlist dropdown is enabled during active sessions
- [x] No TypeScript errors or linting issues
- [x] Smooth UI transition without jarring resets

## Dependencies

- Existing comparison session state management
- Playlist selection UI components
- Session initialization logic