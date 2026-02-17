---
task: 03-restyle-waveform-player
status: done
depends: []
files:
  - path: web/frontend/src/components/WaveformPlayer.tsx
    action: modify
---

# Restyle WaveformPlayer to Obsidian

## Context
Convert WaveformPlayer from emerald/slate theme to obsidian black/amber. Simplify play button, update time display styling.

## Files to Modify
- web/frontend/src/components/WaveformPlayer.tsx (modify) - lines 78-92, 114

## Implementation Details

**Step 1: Update play button styling**

Replace play button (lines 78-92):

```tsx
// FROM:
<button
  onClick={onTogglePlayPause || togglePlayPause}
  className="flex-shrink-0 w-10 h-10 ml-3 mr-2 bg-emerald-500 text-white rounded-full flex items-center justify-center hover:bg-emerald-400 shadow-lg transition-colors"
  aria-label={isPlaying ? 'Pause' : 'Play'}
>

// TO:
<button
  onClick={onTogglePlayPause || togglePlayPause}
  className="w-8 h-8 flex items-center justify-center text-obsidian-accent hover:text-white transition-colors"
  aria-label={isPlaying ? 'Pause' : 'Play'}
>
```

**Step 2: Update icon sizes**

Change icon classes from `w-5 h-5` to `w-4 h-4` (lines 84, 88)

**Step 3: Update time display styling**

Replace time display (line 114):

```tsx
// FROM:
<div className="absolute bottom-1 right-2 z-10 text-[10px] font-mono text-emerald-400/80 bg-slate-900/80 px-1 rounded pointer-events-none">

// TO:
<span className="text-white/30 text-xs font-sf-mono w-20 text-right">
```

**Step 4: Restructure layout to match obsidian**

The overall structure should become:

```tsx
<div className="flex items-center w-full h-full gap-4">
  {/* Play button */}
  <button ...>...</button>

  {/* Waveform container */}
  <div className="flex-1 h-full relative">
    {error && <div className="absolute inset-0 z-20 ...">...</div>}
    <div ref={containerRef} className="w-full h-full" />
  </div>

  {/* Time display */}
  <span className="text-white/30 text-xs font-sf-mono w-20 text-right">
    {formatTime(currentTime)} / {formatTime(duration)}
  </span>
</div>
```

## Verification

```bash
cd web/frontend && npm run dev
```

Navigate to playlist builder, verify waveform plays and displays correctly with obsidian styling.

## Commit

```bash
git add web/frontend/src/components/WaveformPlayer.tsx
git commit -m "style: restyle WaveformPlayer to obsidian theme"
```
