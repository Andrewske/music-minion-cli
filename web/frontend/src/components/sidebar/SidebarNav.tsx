import { useState } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import { House, Clock, Trophy, ListMusic, Layers, Settings, ChevronDown, Users } from 'lucide-react';

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { href: '/', label: 'Home', icon: House },
  { href: '/history', label: 'History', icon: Clock },
  { href: '/artists', label: 'Artists', icon: Users },
  { href: '/comparison', label: 'Comparison', icon: Trophy },
  { href: '/playlist-builder', label: 'Playlist Builder', icon: ListMusic },
  { href: '/playlist-organizer', label: 'Playlist Organizer', icon: Layers },
  { href: '/settings', label: 'Settings', icon: Settings },
];

interface SidebarNavProps {
  isExpanded: boolean;
  onNavigate?: () => void;
}

export function SidebarNav({ isExpanded, onNavigate }: SidebarNavProps): JSX.Element {
  const routerState = useRouterState();
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <nav className="py-2">
      {/* Collapsible header - only when sidebar is expanded */}
      {isExpanded && (
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="w-full flex items-center justify-between px-4 py-2 text-white/60 hover:text-white"
        >
          <span className="text-xs tracking-[0.2em] uppercase">Pages</span>
          <ChevronDown
            className={`w-4 h-4 transition-transform ${isCollapsed ? '-rotate-90' : ''}`}
          />
        </button>
      )}

      {/* Nav items */}
      {!isCollapsed && (
        <div className="flex flex-col gap-1 px-2">
          {navItems.map((item) => {
            const isActive = routerState.location.pathname === item.href;
            const Icon = item.icon;

            return (
              <div key={item.href} className="group relative">
                <Link
                  to={item.href}
                  aria-label={item.label}
                  onClick={onNavigate}
                  className={`flex items-center gap-3 px-3 py-2 rounded transition-colors ${
                    isActive
                      ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent text-obsidian-accent'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-obsidian-accent' : ''}`} />
                  {isExpanded && <span className="text-sm">{item.label}</span>}
                </Link>
                {!isExpanded && (
                  <div
                    className="absolute left-full ml-2 hidden group-hover:block
                              bg-obsidian-surface border border-obsidian-border
                              text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50"
                    role="tooltip"
                  >
                    {item.label}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </nav>
  );
}
