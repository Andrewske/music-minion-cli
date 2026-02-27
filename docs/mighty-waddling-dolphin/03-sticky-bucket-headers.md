---
task: 03-sticky-bucket-headers
status: done
depends: []
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Implement Sticky Bucket Headers

## Context
Make bucket headers stick to the top of viewport while scrolling, ensuring they remain visible when users scroll through unassigned tracks. Critical for mobile UX where screen real estate is limited.

## Files to Modify/Create
- web/frontend/src/pages/PlaylistOrganizer.tsx (modify)

## Implementation Details

### In PlaylistOrganizer.tsx (around line 470-545)

Wrap the BucketList component in a sticky container:

**Before:**
```tsx
{/* Buckets section */}
<BucketList
  buckets={buckets}
  // ... props
/>
```

**After:**
```tsx
{/* Buckets section - sticky container */}
<div className="sticky top-0 z-10 bg-black pb-4">
  <BucketList
    buckets={buckets}
    // ... props
  />
</div>
```

**Key details:**
- `sticky top-0`: Sticks to top of viewport
- `z-10`: Ensures buckets stay above unassigned track table during scroll
- `bg-black`: Prevents content from showing through when scrolling underneath
- `pb-4`: Padding bottom for visual separation from unassigned tracks

## Verification
- Bucket headers stick to top of viewport when scrolling down
- Buckets appear above unassigned tracks (z-index working)
- No visual "bleed through" of content when scrolling (background color working)
- Test on desktop and mobile viewport sizes
- Scroll position doesn't jump or behave unexpectedly
