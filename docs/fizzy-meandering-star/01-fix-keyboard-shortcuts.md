---
task: 01-fix-keyboard-shortcuts
status: done
depends: []
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Fix Shift+Number Keyboard Shortcuts

## Context
The keyboard shortcuts for assigning tracks to buckets (Shift+1 through Shift+0) are completely broken. When Shift is held, the browser reports `e.key` as shifted characters ("!", "@", "#") instead of numbers, causing `parseInt(e.key)` to return `NaN` and the handler to exit early.

## Files to Modify
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify lines 76-102)

## Implementation Details

**Root Cause**: Lines 86-87 in PlaylistOrganizer.tsx
```typescript
const num = parseInt(e.key); // e.key = "!" when Shift+1 is pressed
if (isNaN(num)) return;      // Always returns early
```

**Solution**: Use `e.code` instead, which returns physical key identifiers:
- Shift+1 → `e.code = "Digit1"` (main number row)
- Numpad 1 → `e.code = "Numpad1"` (numpad)
- etc.

**Changes Required**:

Replace lines 86-87:
```typescript
const num = parseInt(e.key);
if (isNaN(num)) return;
```

With:
```typescript
const digitMatch = e.code.match(/^(?:Digit|Numpad)(\d)$/);
if (!digitMatch) return;
const num = parseInt(digitMatch[1]);
```

This approach:
- Supports both main number row (Digit1-9) and numpad (Numpad1-9)
- Browser-consistent across all platforms
- Keyboard-layout independent
- Future-proof (not using deprecated APIs)

**Result**:
- Shift+1 through Shift+9 map to bucket indices 0-8
- Shift+0 maps to bucket index 9 (10th bucket)
- Works with both main keyboard and numpad

## Verification

1. Start web mode: `music-minion --web`
2. Navigate to playlist organizer for any playlist
3. Click an unassigned track to start playing it
4. Press **Shift+1** → Track should assign to first bucket and auto-advance to next track
5. Press **Shift+2**, **Shift+3**, etc. → Should assign to respective buckets
6. Try **Shift+0** → Should assign to 10th bucket (if it exists)
7. Try with **numpad keys** (Shift+Numpad1, etc.) → Should work identically
8. **Edge case**: Press Shift+1 when no buckets exist → Should no-op gracefully (no crash)

**Expected Behavior**:
- Shortcut only works when a track is currently playing
- Shortcut ignored when typing in input/textarea fields
- After assignment, automatically advances to next unassigned track and plays it
