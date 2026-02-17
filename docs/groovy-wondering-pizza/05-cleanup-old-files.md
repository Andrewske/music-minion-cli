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
  - path: web/frontend/src/hooks/useBuilderSession.ts
    action: delete
  - path: web/frontend/src/pages/PlaylistBuilder.tsx
    action: modify
  - path: web/frontend/src/api/builder.ts
    action: modify
  - path: web/backend/routers/builder.py
    action: modify
---

# Delete Old Files and Session Code

## Context
After unification, SmartPlaylistEditor, useSmartPlaylistEditor, and useBuilderSession are no longer needed. Session-related backend code can also be removed since skips are now permanent.

## Files to Delete
- `web/frontend/src/pages/SmartPlaylistEditor.tsx`
- `web/frontend/src/hooks/useSmartPlaylistEditor.ts`
- `web/frontend/src/hooks/useBuilderSession.ts`

## Files to Modify
- `web/frontend/src/pages/PlaylistBuilder.tsx` - remove old imports
- `web/frontend/src/api/builder.ts` - remove session-related functions
- `web/backend/routers/builder.py` - remove session endpoints (optional, can keep for backwards compat)

## Implementation Details

### Delete Frontend Files
```bash
rm web/frontend/src/pages/SmartPlaylistEditor.tsx
rm web/frontend/src/hooks/useSmartPlaylistEditor.ts
rm web/frontend/src/hooks/useBuilderSession.ts
```

### Clean PlaylistBuilder.tsx Imports
Remove:
```typescript
import { SmartPlaylistEditor } from './SmartPlaylistEditor';
import { useBuilderSession } from '../hooks/useBuilderSession';
```

### Clean builder.ts API (optional)
Remove session-related functions if no longer used:
- `startSession`
- `getSession`
- `endSession`

### Check for Other References
```bash
grep -r "SmartPlaylistEditor" web/frontend/src/
grep -r "useSmartPlaylistEditor" web/frontend/src/
grep -r "useBuilderSession" web/frontend/src/
grep -r "startSession\|endSession\|getSession" web/frontend/src/
```

## Verification
1. No TypeScript compilation errors
2. No dangling imports
3. Smart playlist builder route still works (via unified PlaylistBuilder)
4. Manual playlist builder works without sessions
5. `npm run build` succeeds
6. No references to deleted files remain
