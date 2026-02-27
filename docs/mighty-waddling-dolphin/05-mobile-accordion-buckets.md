---
task: 05-mobile-accordion-buckets
status: pending
depends: []
files:
  - path: web/frontend/src/hooks/useIsMobile.ts
    action: create
  - path: web/frontend/src/components/organizer/BucketList.tsx
    action: modify
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
---

# Implement Mobile Accordion for Buckets

## Context
Reduce vertical space on mobile by collapsing buckets by default and allowing only one expanded at a time. Desktop retains current behavior (user controls expand/collapse independently).

## Files to Modify/Create
- web/frontend/src/hooks/useIsMobile.ts (create)
- web/frontend/src/components/organizer/BucketList.tsx (modify)
- web/frontend/src/components/organizer/Bucket.tsx (modify)

## Implementation Details

### 0. Create shared mobile detection hook

**Create new file: `web/frontend/src/hooks/useIsMobile.ts`**
```typescript
import { useState, useEffect } from 'react';

export function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth < breakpoint
  );

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < breakpoint);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, [breakpoint]);

  return isMobile;
}
```

### 1. In BucketList.tsx

**Add state to track expanded bucket on mobile:**
```typescript
import { useState } from 'react';
import { useIsMobile } from '../../hooks/useIsMobile';

export function BucketList({
  buckets,
  // ... other props
}: BucketListProps): JSX.Element {
  // Track which bucket is expanded on mobile (null = all collapsed)
  const [mobileExpandedBucketId, setMobileExpandedBucketId] = useState<string | null>(null);

  // Detect mobile viewport using shared hook
  const isMobile = useIsMobile();

  // ... rest of component
}
```

**Pass mobile accordion props to BucketComponent:**
```typescript
<BucketComponent
  key={bucket.id}
  bucket={bucket}
  // ... existing props
  isMobile={isMobile}
  isMobileExpanded={mobileExpandedBucketId === bucket.id}
  onMobileToggle={() => {
    // Toggle: if already expanded, collapse; otherwise expand this one
    setMobileExpandedBucketId(
      mobileExpandedBucketId === bucket.id ? null : bucket.id
    );
  }}
/>
```

### 2. In Bucket.tsx

**Add new props:**
```typescript
interface BucketComponentProps {
  // ... existing props
  isMobile?: boolean;
  isMobileExpanded?: boolean;
  onMobileToggle?: () => void;
}
```

**Update expand/collapse logic:**
```typescript
export function BucketComponent({
  bucket,
  // ... existing props
  isMobile = false,
  isMobileExpanded = false,
  onMobileToggle,
}: BucketComponentProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);

  // Determine actual expanded state based on mobile/desktop mode
  const actuallyExpanded = isMobile ? isMobileExpanded : isExpanded;

  // Handle expand/collapse button click
  const handleToggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isMobile && onMobileToggle) {
      onMobileToggle();
    } else {
      setIsExpanded(!isExpanded);
    }
  };

  // ... rest of component
}
```

**Update expand/collapse button:**
```typescript
<button
  type="button"
  onClick={handleToggleExpand}
  className="text-white/50 hover:text-white/80 transition-colors"
>
  {actuallyExpanded ? (
    <ChevronDown className="w-4 h-4" />
  ) : (
    <ChevronRight className="w-4 h-4" />
  )}
</button>
```

**Update track list conditional:**
```typescript
{/* Expanded track list */}
{actuallyExpanded && (
  <div className="border-t border-obsidian-border">
    {/* ... track list content */}
  </div>
)}
```

**Update auto-expand on drag hover** (around line 101):
```typescript
useEffect(() => {
  if (isOver && !actuallyExpanded) {
    const timer = setTimeout(() => {
      if (isMobile && onMobileToggle) {
        onMobileToggle();
      } else {
        setIsExpanded(true);
      }
    }, 500);
    return () => clearTimeout(timer);
  }
}, [isOver, actuallyExpanded, isMobile, onMobileToggle]);
```

## Verification

### Desktop (>= 768px)
- Buckets expand/collapse independently (current behavior preserved)
- Multiple buckets can be expanded simultaneously
- Expand/collapse state persists during session

### Mobile (< 768px)
- All buckets collapsed by default on initial load
- Clicking expand icon on one bucket expands it
- Expanding a different bucket auto-collapses the previously expanded one
- Only one bucket expanded at a time
- Dragging over a bucket auto-expands it after 500ms

### Both
- Resize from desktop to mobile: accordion behavior activates
- Resize from mobile to desktop: independent expand/collapse resumes
- No console errors or state management issues
