import { ChevronLeft, ChevronRight } from 'lucide-react';

interface SidebarToggleProps {
  isExpanded: boolean;
  onToggle: () => void;
}

export function SidebarToggle({ isExpanded, onToggle }: SidebarToggleProps): JSX.Element {
  return (
    <button
      onClick={onToggle}
      className="p-2 text-white/60 hover:text-white hover:bg-white/5 rounded transition-colors"
      aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
    >
      {isExpanded ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
    </button>
  );
}
