---
task: 04-restyle-track-queue-table
status: done
depends: []
files:
  - path: web/frontend/src/components/builder/TrackQueueTable.tsx
    action: modify
---

# Restyle TrackQueueTable to Obsidian

## Context
Convert TrackQueueTable from slate theme to obsidian black/amber. Update row highlights, headers, and cells.

## Files to Modify
- web/frontend/src/components/builder/TrackQueueTable.tsx (modify) - lines 152-165, 180-187, 236-237

## Implementation Details

**Step 1: Update row highlight classes**

Replace `getRowClasses` function (lines 152-165):

```tsx
const getRowClasses = (index: number, trackId: number): string => {
  const isQueue = index === queueIndex;
  const isPlaying = trackId === nowPlayingId;

  let classes = 'cursor-pointer hover:bg-white/5 transition-colors ';

  if (isPlaying) {
    classes += 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent ';
  } else if (isQueue) {
    classes += 'bg-white/5 ';
  }

  return classes;
};
```

**Step 2: Update container styling**

Replace container div (line 180):

```tsx
// FROM:
<div className="bg-slate-800 rounded-lg overflow-hidden">

// TO:
<div className="border-t border-obsidian-border">
```

**Step 3: Update header styling**

Replace thead (line 187):

```tsx
// FROM:
<thead className="bg-slate-700" style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}>

// TO:
<thead className="border-b border-obsidian-border" style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}>
```

**Step 4: Update header cell styling**

Replace th className (lines 193):

```tsx
// FROM:
className="px-3 py-2 text-left cursor-pointer hover:bg-slate-600 select-none"

// TO:
className={`px-3 py-2 text-left cursor-pointer select-none text-xs tracking-wider uppercase transition-colors
  ${sorting.find(s => s.id === header.id) ? 'text-obsidian-accent' : 'text-white/30 hover:text-white/60'}`}
```

**Step 5: Update cell styling**

Replace td className (line 236-237):

```tsx
// FROM:
className="px-3 py-2 border-b border-slate-700 overflow-hidden"

// TO:
className="px-3 py-2 border-b border-obsidian-border/50 overflow-hidden text-white/50"
```

**Step 6: Update loading indicator**

Replace loading div (lines 255-257):

```tsx
// FROM:
<div className="text-center py-2 text-slate-400 text-sm">

// TO:
<div className="w-full py-2 text-white/30 text-xs text-center">
```

## Verification

```bash
cd web/frontend && npm run dev
```

Navigate to playlist builder, verify table has obsidian styling.

## Commit

```bash
git add web/frontend/src/components/builder/TrackQueueTable.tsx
git commit -m "style: restyle TrackQueueTable to obsidian theme"
```
