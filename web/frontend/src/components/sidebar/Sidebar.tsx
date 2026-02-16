import { useState, useEffect } from 'react';
import { SidebarNav } from './SidebarNav';
import { SidebarToggle } from './SidebarToggle';
import { SidebarSection } from './SidebarSection';

interface SidebarProps {
  children?: React.ReactNode;
}

export function Sidebar({ children }: SidebarProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(() => {
    const stored = localStorage.getItem('music-minion-sidebar-expanded');
    return stored !== null ? JSON.parse(stored) : true;
  });

  // Persist to localStorage
  useEffect(() => {
    localStorage.setItem('music-minion-sidebar-expanded', JSON.stringify(isExpanded));
  }, [isExpanded]);

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
        {isExpanded && <SidebarToggle isExpanded={isExpanded} onToggle={() => setIsExpanded(!isExpanded)} />}
      </div>

      {/* Navigation */}
      <SidebarNav isExpanded={isExpanded} />

      {/* Divider */}
      {children && <div className="border-t border-obsidian-border" />}

      {/* Route-aware context section */}
      {children && <div className="flex-1 overflow-y-auto">{children}</div>}

      {/* Collapsed state toggle at bottom */}
      {!isExpanded && (
        <div className="border-t border-obsidian-border p-2 flex justify-center">
          <SidebarToggle isExpanded={isExpanded} onToggle={() => setIsExpanded(!isExpanded)} />
        </div>
      )}
    </aside>
  );
}

// Re-export SidebarSection for convenience
export { SidebarSection };
