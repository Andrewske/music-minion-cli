---
task: 02-mobile-sidebar
status: done
depends: [01-create-sidebar-components]
files:
  - path: web/frontend/src/components/sidebar/MobileHeader.tsx
    action: create
  - path: web/frontend/src/components/playlist-builder/MobileHeader.tsx
    action: delete
---

# Mobile Sidebar Implementation

## Context
Mobile devices need a different UX - hamburger menu with slide-out sheet. This follows the glade-demo pattern while maintaining obsidian styling. Replaces the existing playlist-builder MobileHeader with a global mobile header.

## Files to Modify/Create
- `web/frontend/src/components/sidebar/MobileHeader.tsx` (new)
- `web/frontend/src/components/playlist-builder/MobileHeader.tsx` (delete)

Note: Reuse existing `web/frontend/src/components/ui/sheet.tsx` - already has Radix Dialog primitives with slide animations.

## Implementation Details

### MobileHeader.tsx
Fixed header at top (mobile only):
```tsx
import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Sheet, SheetContent } from '../ui/sheet';
import { Sidebar } from './Sidebar';

export function MobileHeader(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-12
                       bg-black border-b border-obsidian-border
                       flex items-center px-4 md:hidden">
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex h-8 w-8 items-center justify-center rounded
                     text-white/60 hover:text-white transition-colors"
          aria-label={isOpen ? 'Close menu' : 'Open menu'}
        >
          {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <SheetContent side="left" className="w-[280px] p-0">
          {/* Full sidebar content - always expanded in mobile sheet */}
          <Sidebar isExpanded={true} isMobile={true} onNavigate={() => setIsOpen(false)} />
        </SheetContent>
      </Sheet>

      <span className="ml-4 text-white font-medium">Music Minion</span>
    </header>
  );
}
```

### Sidebar Props for Mobile
Add props to Sidebar component:
- `isMobile?: boolean` - when true, skip toggle button
- `onNavigate?: () => void` - callback to close sheet after nav click

### Responsive Logic
- `md:hidden` on MobileHeader
- `hidden md:flex` on desktop Sidebar
- Content area needs `pt-12 md:pt-0` to account for mobile header

## Verification
1. Resize browser to mobile width (<768px)
2. Hamburger icon visible, sidebar hidden
3. Click hamburger - sheet slides in from left
4. Navigate via sheet - sheet closes, page changes
5. Click outside sheet or X - sheet closes
