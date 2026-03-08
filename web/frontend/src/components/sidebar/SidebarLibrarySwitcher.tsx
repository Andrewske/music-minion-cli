import { HardDrive, Cloud } from 'lucide-react';
import { useLibraryStore } from '../../stores/libraryStore';
import { cn } from '../../lib/utils';

interface SidebarLibrarySwitcherProps {
  sidebarExpanded: boolean;
}

export function SidebarLibrarySwitcher({ sidebarExpanded }: SidebarLibrarySwitcherProps): JSX.Element {
  const { activeLibrary, setActiveLibrary } = useLibraryStore();

  return (
    <div className={cn(
      "border-b border-obsidian-border",
      sidebarExpanded ? "px-4 py-3" : "px-2 py-3"
    )}>
      <div className={cn(
        "flex gap-1 p-1 bg-obsidian-surface rounded-lg",
        !sidebarExpanded && "flex-col"
      )}>
        <button
          onClick={() => setActiveLibrary('local')}
          title={!sidebarExpanded ? "Local Library" : undefined}
          className={cn(
            "flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-all duration-200",
            sidebarExpanded ? "flex-1 px-3 py-2" : "p-2",
            activeLibrary === 'local'
              ? "bg-obsidian-accent text-black"
              : "text-white/60 hover:text-white hover:bg-white/5"
          )}
        >
          <HardDrive className="w-4 h-4" />
          {sidebarExpanded && <span>Local</span>}
        </button>
        <button
          onClick={() => setActiveLibrary('soundcloud')}
          title={!sidebarExpanded ? "SoundCloud" : undefined}
          className={cn(
            "flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-all duration-200",
            sidebarExpanded ? "flex-1 px-3 py-2" : "p-2",
            activeLibrary === 'soundcloud'
              ? "bg-[#ff5500] text-white"
              : "text-white/60 hover:text-white hover:bg-white/5"
          )}
        >
          <Cloud className="w-4 h-4" />
          {sidebarExpanded && <span>SoundCloud</span>}
        </button>
      </div>
    </div>
  );
}
