---
task: 03-verify-end-to-end
status: pending
depends:
  - 01-fix-get-next-playlist-pair
  - 02-fix-get-playlist-comparison-progress
files: []
---

# End-to-End Verification

## Context
Verify the fix works for smart playlists while not breaking manual playlists.

## Implementation Details

Manual testing steps:

1. **Start the web app:**
```bash
uv run music-minion --web
```

2. **Test smart playlist comparison:**
   - Navigate to Comparisons page in browser (localhost:5173)
   - Select a smart playlist from the dropdown
   - Confirm comparison pairs load without 400 error
   - Complete 2-3 comparisons to verify recording works

3. **Test manual playlist comparison (regression check):**
   - Select a manual playlist
   - Confirm comparison pairs still load correctly
   - Complete 1-2 comparisons

4. **Verify progress tracking:**
   - Check that progress percentage updates correctly for both types

## Verification
No automated test - manual browser verification required.
