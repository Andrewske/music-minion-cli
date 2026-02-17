---
task: 05-cleanup-old-files
status: pending
depends:
  - 03-unify-playlist-builder
  - 04-restyle-filter-panel
files:
  - path: web/frontend/src/pages/SmartPlaylistEditor.tsx
    action: delete
  - path: web/frontend/src/hooks/useSmartPlaylistEditor.ts
    action: delete
  - path: web/frontend/src/pages/PlaylistBuilder.tsx
    action: modify
---

# Delete SmartPlaylistEditor and Cleanup

## Context
After unification, SmartPlaylistEditor and its hook are no longer needed. Remove them and clean up any remaining imports.

## Files to Modify/Create
- `web/frontend/src/pages/SmartPlaylistEditor.tsx` (delete)
- `web/frontend/src/hooks/useSmartPlaylistEditor.ts` (delete)
- `web/frontend/src/pages/PlaylistBuilder.tsx` (modify - remove import)

## Implementation Details

### Delete Files
```bash
rm web/frontend/src/pages/SmartPlaylistEditor.tsx
rm web/frontend/src/hooks/useSmartPlaylistEditor.ts
```

### Clean PlaylistBuilder.tsx Import
Remove:
```typescript
import { SmartPlaylistEditor } from './SmartPlaylistEditor';
```

### Check for Other References
Search codebase for any other imports of deleted files:
```bash
grep -r "SmartPlaylistEditor" web/frontend/src/
grep -r "useSmartPlaylistEditor" web/frontend/src/
```

## Verification
1. No TypeScript compilation errors
2. No dangling imports
3. Smart playlist builder route still works (via unified PlaylistBuilder)
4. `npm run build` succeeds
