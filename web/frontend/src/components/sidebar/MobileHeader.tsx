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
