import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface SidebarSectionProps {
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  sidebarExpanded: boolean;
}

export function SidebarSection({
  title,
  children,
  defaultExpanded = true,
  sidebarExpanded,
}: SidebarSectionProps): JSX.Element | null {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Hide entire section when sidebar is collapsed
  if (!sidebarExpanded) return null;

  return (
    <div className="border-t border-obsidian-border">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-white/60 hover:text-white"
      >
        <span className="text-xs tracking-[0.2em] uppercase">{title}</span>
        <ChevronDown
          className={`w-4 h-4 transition-transform ${isExpanded ? '' : '-rotate-90'}`}
        />
      </button>
      {isExpanded && <div className="px-2 pb-2 overflow-y-auto max-h-[30vh]">{children}</div>}
    </div>
  );
}
