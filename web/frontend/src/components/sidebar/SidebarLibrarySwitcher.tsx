import { useLibraryStore } from '../../stores/libraryStore';

interface SidebarLibrarySwitcherProps {
  sidebarExpanded: boolean;
}

export function SidebarLibrarySwitcher({ sidebarExpanded }: SidebarLibrarySwitcherProps): JSX.Element | null {
  const { activeLibrary, setActiveLibrary } = useLibraryStore();

  if (!sidebarExpanded) return null;

  return (
    <div className="px-4 py-3 border-b border-obsidian-border">
      <label className="block text-xs text-white/50 uppercase tracking-wider mb-2">
        Library
      </label>
      <select
        value={activeLibrary}
        onChange={(e) => setActiveLibrary(e.target.value as 'local' | 'soundcloud')}
        className="w-full text-sm bg-obsidian-bg text-white border border-obsidian-border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
      >
        <option value="local">Local Library</option>
        <option value="soundcloud">SoundCloud</option>
      </select>
    </div>
  );
}
