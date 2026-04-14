import type { ReactElement } from 'react';
import { Search, Check } from 'lucide-react';

type ArtistSource = 'all' | 'soundcloud' | 'local' | 'following';
type ArtistSort = 'name' | 'rank' | 'library' | 'reposts' | 'hit_rate' | 'noise' | 'last_loved';

interface ArtistFiltersBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  source: ArtistSource;
  onSourceChange: (value: ArtistSource) => void;
  sort: ArtistSort;
  onSortChange: (value: ArtistSort) => void;
  paretoActive: boolean;
  onParetoClear: () => void;
  paretoCount: number;
  resultCount: number;
}

const SELECT_CLASS =
  'bg-obsidian-surface border border-obsidian-border px-3 py-1.5 text-sm text-white font-sf-mono focus:border-obsidian-accent/40 focus:outline-none';

export function ArtistFiltersBar({
  search,
  onSearchChange,
  source,
  onSourceChange,
  sort,
  onSortChange,
  paretoActive,
  onParetoClear,
  paretoCount,
  resultCount,
}: ArtistFiltersBarProps): ReactElement {
  return (
    <div className="sticky top-0 z-10 bg-black/80 backdrop-blur-sm border-b border-obsidian-border -mx-6 px-6 py-3 flex items-center gap-3 flex-wrap">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30 pointer-events-none" />
        <input
          type="text"
          placeholder="Search artists…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full bg-obsidian-surface border border-obsidian-border px-3 py-1.5 pl-9 text-sm text-white placeholder:text-white/40 focus:border-obsidian-accent/40 focus:outline-none"
        />
      </div>

      {/* Source */}
      <select
        value={source}
        onChange={(e) => onSourceChange(e.target.value as ArtistSource)}
        className={SELECT_CLASS}
      >
        <option value="all">All</option>
        <option value="soundcloud">SoundCloud</option>
        <option value="local">Local</option>
        <option value="following">Following</option>
      </select>

      {/* Sort */}
      <select
        value={sort}
        onChange={(e) => onSortChange(e.target.value as ArtistSort)}
        className={SELECT_CLASS}
      >
        <option value="name">Name</option>
        <option value="rank">Rank</option>
        <option value="library">Library count</option>
        <option value="reposts">Reposts</option>
        <option value="hit_rate">Hit rate</option>
        <option value="noise">Feed noise</option>
        <option value="last_loved">Last loved</option>
      </select>

      {/* Pareto chip — only when active */}
      {paretoActive && (
        <button
          type="button"
          onClick={onParetoClear}
          className="bg-amber-500/10 border border-amber-500/40 px-3 py-1.5 text-xs font-sf-mono text-amber-400 flex items-center gap-1.5 hover:bg-amber-500/20 transition-colors"
        >
          <Check className="w-3 h-3" />
          Pareto: {paretoCount}
        </button>
      )}

      {/* Result count */}
      <span className="ml-auto font-sf-mono text-xs text-white/40">{resultCount} results</span>
    </div>
  );
}
