---
task: 07-cleanup-and-verify
status: pending
depends: [06-rewrite-playlist-builder]
files:
  - path: web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx
    action: delete
---

# Delete ObsidianMinimalBuilder and Final Verification

## Context
Remove the now-merged ObsidianMinimalBuilder component and verify the full implementation works.

## Files to Delete
- web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx (delete)

## Implementation Details

**Step 1: Search for imports of ObsidianMinimalBuilder**

```bash
grep -r "ObsidianMinimalBuilder" web/frontend/src/
```

If any imports exist, remove them.

**Step 2: Delete the file**

```bash
rm web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx
```

**Step 3: Run full build**

```bash
cd web/frontend && npm run build
```

Expected: Build succeeds with no errors

**Step 4: Test playlist builder flow**

1. Start dev server: `npm run dev`
2. Navigate to a manual playlist
3. Verify "Begin" button appears with obsidian styling
4. Start session, verify track display
5. Test waveform playback
6. Test add/skip buttons
7. Test emoji actions
8. Test track queue (desktop table view)
9. Test mobile view (card layout)
10. Verify loop toggle works

## Verification

```bash
cd web/frontend && npm run build
```

Expected: Build succeeds, all features work as described above.

## Commit

```bash
git add -A
git commit -m "chore: delete ObsidianMinimalBuilder (merged into PlaylistBuilder)"
```
