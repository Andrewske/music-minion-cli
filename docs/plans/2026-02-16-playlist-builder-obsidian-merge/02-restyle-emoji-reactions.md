---
task: 02-restyle-emoji-reactions
status: done
depends: [01-clean-up-emoji-debug]
files:
  - path: web/frontend/src/components/EmojiReactions.tsx
    action: modify
---

# Restyle EmojiReactions to Obsidian

## Context
Convert EmojiReactions from slate/emerald theme to obsidian black/amber design. Add hover × indicator for removal.

## Files to Modify
- web/frontend/src/components/EmojiReactions.tsx (modify) - lines 80-95, 99-111

## Implementation Details

**Step 1: Update emoji button styling**

Replace the button className (around line 83-86):

```tsx
// FROM:
className={`
  ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1'}
  bg-slate-800 hover:bg-red-600 rounded-md transition-colors flex items-center justify-center
`}

// TO:
className={`
  relative group ${compact ? 'text-sm' : 'text-base'}
  leading-none hover:opacity-70 disabled:opacity-30 transition-opacity
`}
```

**Step 2: Add × indicator on hover**

After `<EmojiDisplay ... />` (around line 93), add:

```tsx
<span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
  <span className="text-obsidian-accent text-xs font-bold">×</span>
</span>
```

**Step 3: Update add button styling**

Replace add button className (around line 103-107):

```tsx
// FROM:
className={`text-2xl font-normal transition-colors ${
  isAdding
    ? 'text-emerald-500 opacity-50 cursor-not-allowed'
    : 'text-emerald-500 hover:text-emerald-400'
}`}

// TO:
className={`text-sm font-bold transition-colors ${
  isAdding
    ? 'text-green-500 opacity-30 cursor-not-allowed'
    : 'text-green-500 hover:text-green-400'
}`}
```

## Verification

```bash
cd web/frontend && npm run dev
```

Navigate to a page with emoji actions, verify obsidian styling with hover × indicator.

## Commit

```bash
git add web/frontend/src/components/EmojiReactions.tsx
git commit -m "style: restyle EmojiReactions to obsidian theme"
```
