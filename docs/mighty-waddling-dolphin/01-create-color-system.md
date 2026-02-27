---
task: 01-create-color-system
status: done
depends: []
files:
  - path: web/frontend/src/constants/bucketColors.ts
    action: create
---

# Create Bucket Color System

## Context
Establish a color palette for bucket visual identity. Each bucket gets a unique color (cycling through 10 colors) used for border styling and mobile indicators. This is the foundation for all visual feedback features.

## Files to Modify/Create
- web/frontend/src/constants/bucketColors.ts (new)

## Implementation Details

Create new file: `web/frontend/src/constants/bucketColors.ts`

```typescript
export const BUCKET_COLORS = [
  'rgb(239, 68, 68)',   // red-500
  'rgb(249, 115, 22)',  // orange-500
  'rgb(234, 179, 8)',   // yellow-500
  'rgb(34, 197, 94)',   // green-500
  'rgb(6, 182, 212)',   // cyan-500
  'rgb(59, 130, 246)',  // blue-500
  'rgb(147, 51, 234)',  // purple-500
  'rgb(236, 72, 153)',  // pink-500
  'rgb(168, 85, 247)',  // violet-500
  'rgb(20, 184, 166)',  // teal-500
] as const;

export function getBucketColor(bucketIndex: number): string {
  return BUCKET_COLORS[bucketIndex % BUCKET_COLORS.length];
}
```

## Verification
- File created at correct path
- BUCKET_COLORS array has 10 colors
- getBucketColor function returns correct color for index 0-9
- getBucketColor correctly cycles for index >= 10 (e.g., index 10 returns same as index 0)

## Future Considerations
- Validate color palette against WCAG AA contrast ratios for accessibility
- Test colors with color blindness simulators (particularly red-green deficiency)
