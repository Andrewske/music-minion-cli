import { useState, useEffect, Children, isValidElement, cloneElement, type ReactElement } from 'react';
import { SidebarNav } from './SidebarNav';
import { SidebarToggle } from './SidebarToggle';
import { SidebarSection } from './SidebarSection';

interface SidebarProps {
  children?: React.ReactNode;
  isExpanded?: boolean;
  isMobile?: boolean;
  onNavigate?: () => void;
}

interface SidebarChildProps {
  sidebarExpanded: boolean;
}

export function Sidebar({ children, isExpanded: controlledExpanded, isMobile = false, onNavigate }: SidebarProps): JSX.Element {
  const [internalExpanded, setInternalExpanded] = useState(() => {
    const stored = localStorage.getItem('music-minion-sidebar-expanded');
    return stored !== null ? JSON.parse(stored) : true;
  });

  // Use controlled state if provided (mobile), otherwise use internal state (desktop)
  const isExpanded = controlledExpanded !== undefined ? controlledExpanded : internalExpanded;

  // Persist to localStorage (desktop only)
  useEffect(() => {
    if (!isMobile && controlledExpanded === undefined) {
      localStorage.setItem('music-minion-sidebar-expanded', JSON.stringify(internalExpanded));
    }
  }, [internalExpanded, isMobile, controlledExpanded]);

  return (
    <aside
      className={`flex flex-col bg-black border-r border-obsidian-border h-[calc(100vh-64px)] transition-all duration-300 ease-in-out ${
        isExpanded ? 'w-[280px]' : 'w-[72px]'
      }`}
    >
      {/* Header with logo and toggle */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-obsidian-border">
        {isExpanded ? (
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-white">Music Minion</span>
          </div>
        ) : (
          <div className="flex items-center justify-center w-full">
            <span className="text-lg font-bold text-obsidian-accent">M</span>
          </div>
        )}
        {isExpanded && !isMobile && <SidebarToggle isExpanded={isExpanded} onToggle={() => setInternalExpanded(!internalExpanded)} />}
      </div>

      {/* Navigation */}
      <SidebarNav isExpanded={isExpanded} onNavigate={onNavigate} />

      {/* Divider */}
      {children && <div className="border-t border-obsidian-border" />}

      {/* Route-aware context section */}
      {children && (
        <div className="flex-1 overflow-y-auto">
          {Children.map(children, (child) =>
            isValidElement(child)
              ? cloneElement(child as ReactElement<SidebarChildProps>, { sidebarExpanded: isExpanded })
              : child
          )}
        </div>
      )}

      {/* Collapsed state toggle at bottom */}
      {!isExpanded && !isMobile && (
        <div className="border-t border-obsidian-border p-2 flex justify-center">
          <SidebarToggle isExpanded={isExpanded} onToggle={() => setInternalExpanded(!internalExpanded)} />
        </div>
      )}
    </aside>
  );
}

// Re-export SidebarSection for convenience
export { SidebarSection };
