import { HardDrive, Cloud } from 'lucide-react';
import { useLibraryStore } from '../../stores/libraryStore';
import { cn } from '../../lib/utils';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '../ui/dropdown-menu';

const libraries = [
  { id: 'local' as const, label: 'Local', icon: HardDrive },
  { id: 'soundcloud' as const, label: 'SoundCloud', icon: Cloud },
];

interface SidebarLibrarySwitcherProps {
  isExpanded: boolean;
}

export function SidebarLibrarySwitcher({ isExpanded }: SidebarLibrarySwitcherProps): JSX.Element {
  const { activeLibrary, setActiveLibrary } = useLibraryStore();

  const active = libraries.find((l) => l.id === activeLibrary) ?? libraries[0];
  const ActiveIcon = active.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          title={active.label}
          className={cn(
            "p-1.5 rounded-md transition-colors",
            activeLibrary === 'soundcloud'
              ? "text-[#ff5500] hover:bg-[#ff5500]/10"
              : "text-white/60 hover:text-white hover:bg-white/10"
          )}
        >
          <ActiveIcon className="w-5 h-5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={isExpanded ? "start" : "center"} side="bottom">
        {libraries.map((lib) => {
          const Icon = lib.icon;
          const isActive = activeLibrary === lib.id;
          return (
            <DropdownMenuItem
              key={lib.id}
              onClick={() => setActiveLibrary(lib.id)}
              className={cn(
                "flex items-center gap-3 cursor-pointer",
                isActive && "text-obsidian-accent"
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{lib.label}</span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
