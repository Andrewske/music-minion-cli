---
task: 06-cleanup-and-verify
status: done
depends: [04-smartplaylist-global-player, 05-comparison-global-player]
files: []
---

# Cleanup and End-to-End Verification

## Context
Final task to clean up any orphaned code and verify the complete integration works end-to-end.

## Files to Modify/Create
- None (verification only)

## Implementation Details

### 1. Search for orphaned references

Check for any remaining references to removed code:
```bash
rg "useAudioPlayer" web/frontend/src/
rg "selectAndPlay" web/frontend/src/
rg "setIsPlaying.*comparison" web/frontend/src/
```

Fix any found references.

### 2. Type check

```bash
cd web/frontend && npx tsc --noEmit
```

Fix any type errors.

### 3. Lint check

```bash
cd web/frontend && npm run lint
```

Fix any lint errors.

## Verification

### Full test sequence:

1. **Start app:**
   ```bash
   music-minion --web
   ```

2. **Global player test:**
   - Navigate to library
   - Double-click track → PlayerBar shows track, audio plays
   - Click pause → audio pauses
   - Click play → audio resumes

3. **Playlist builder test:**
   - Navigate to smart playlist editor
   - Click track in table → replaces global player, audio plays
   - Seek via waveform → global player seeks
   - Verify PlayerBar shows same track

4. **Comparison mode test:**
   - Start comparison session
   - Tap track A → plays via global player
   - Let track finish → auto-switches to track B
   - Let track B finish → auto-switches to track A
   - Verify PlayerBar shows current comparison track

5. **No dual playback test:**
   - Play track in library
   - Switch to builder, click different track
   - Verify first track stops, second plays
   - Switch to comparison, tap track
   - Verify previous track stops, comparison track plays

6. **WebSocket sync test:**
   - Open second browser tab
   - Play track in first tab
   - Verify second tab shows same track info
   - Pause in second tab
   - Verify first tab reflects pause

### Success criteria:
- Only ONE audio stream plays at any time
- All waveforms sync with global player
- A/B comparison looping works
- WebSocket device sync works
- No console errors
