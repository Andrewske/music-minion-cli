import { Link, useRouterState } from '@tanstack/react-router';
import { Settings } from 'lucide-react';

interface SidebarSettingsLinkProps {
  isExpanded: boolean;
  onNavigate?: () => void;
}

export function SidebarSettingsLink({ isExpanded, onNavigate }: SidebarSettingsLinkProps): JSX.Element {
  const routerState = useRouterState();
  const isActive = routerState.location.pathname === '/settings';

  return (
    <Link
      to="/settings"
      onClick={onNavigate}
      className={`flex items-center gap-3 px-4 py-3 transition-colors relative group ${
        isActive
          ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent text-obsidian-accent'
          : 'text-white/60 hover:text-white hover:bg-white/5'
      }`}
    >
      <Settings className="w-5 h-5 flex-shrink-0" />
      {isExpanded && <span className="text-sm">Settings</span>}

      {/* Tooltip for collapsed state */}
      {!isExpanded && (
        <div className="absolute left-full ml-2 px-3 py-1.5 bg-obsidian-surface border border-obsidian-border
                        text-white text-sm rounded opacity-0 group-hover:opacity-100
                        pointer-events-none transition-opacity z-50 whitespace-nowrap">
          Settings
        </div>
      )}
    </Link>
  );
}
