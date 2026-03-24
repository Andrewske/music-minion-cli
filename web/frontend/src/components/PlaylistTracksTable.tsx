import { useState, useMemo, useCallback, useEffect } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import type { PlaylistTrackEntry } from '../types';
import { EmojiTrackActions } from './EmojiTrackActions';

interface PlaylistTracksTableProps {
  tracks: PlaylistTrackEntry[];
}

type SortField = 'rating' | 'title' | 'artist' | 'wins' | 'losses' | 'comparison_count';
type SortDirection = 'asc' | 'desc';

export function PlaylistTracksTable({ tracks }: PlaylistTracksTableProps): JSX.Element {
  const [sortField, setSortField] = useState<SortField>('rating');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  // Local state for tracks to allow emoji updates
  const [localTracks, setLocalTracks] = useState<PlaylistTrackEntry[]>(tracks);

  // Sync local state when tracks prop changes (e.g., on refetch)
  useEffect(() => {
    setLocalTracks(tracks);
  }, [tracks]);

  const sortedTracks = useMemo(() => {
    return [...localTracks].sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;

      switch (sortField) {
        case 'rating':
          aValue = a.rating;
          bValue = b.rating;
          break;
        case 'title':
          aValue = a.title.toLowerCase();
          bValue = b.title.toLowerCase();
          break;
        case 'artist':
          aValue = (a.artist || '').toLowerCase();
          bValue = (b.artist || '').toLowerCase();
          break;
        case 'wins':
          aValue = a.wins;
          bValue = b.wins;
          break;
        case 'losses':
          aValue = a.losses;
          bValue = b.losses;
          break;
        case 'comparison_count':
          aValue = a.comparison_count;
          bValue = b.comparison_count;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) {
        return sortDirection === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortDirection === 'asc' ? 1 : -1;
      }
      return 0;
    });
  }, [localTracks, sortField, sortDirection]);

  const handleSort = (field: SortField): void => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const getSortIcon = (field: SortField): string => {
    if (sortField !== field) {
      return '↕️';
    }
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  const handleTrackUpdate = useCallback((updatedTrack: { id: number; emojis?: string[] }): void => {
    setLocalTracks((prev) =>
      prev.map((track) =>
        track.id === updatedTrack.id
          ? { ...track, emojis: updatedTrack.emojis }
          : track
      )
    );
  }, []);

  const sortFieldLabels: Record<SortField, string> = {
    rating: 'Rating',
    title: 'Title',
    artist: 'Artist',
    wins: 'Wins',
    losses: 'Losses',
    comparison_count: 'Total',
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 md:p-6">
      <h3 className="text-lg font-semibold text-slate-200 mb-4">All Tracks</h3>

      {/* Mobile card view */}
      <div className="md:hidden">
        {/* Sort controls */}
        <div className="flex items-center gap-2 py-2 mb-2 border-b border-slate-800">
          <span className="text-white/30 text-xs">Sort:</span>
          <select
            value={sortField}
            onChange={(e) => setSortField(e.target.value as SortField)}
            className="bg-slate-800 text-slate-200 text-sm rounded px-2 py-1 border border-slate-700"
          >
            {(Object.keys(sortFieldLabels) as SortField[]).map((field) => (
              <option key={field} value={field}>{sortFieldLabels[field]}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
            className="text-slate-400 hover:text-slate-200 p-1"
            aria-label={`Sort ${sortDirection === 'asc' ? 'descending' : 'ascending'}`}
          >
            {sortDirection === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {/* Cards */}
        <div className="space-y-0">
          {sortedTracks.map((track) => (
            <div key={track.id} className="py-3 border-b border-slate-800/50">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-200 truncate">{track.title}</div>
                  <div className="text-xs text-slate-400 truncate">{track.artist || 'Unknown Artist'}</div>
                </div>
                <div className="text-sm font-mono text-slate-200 shrink-0">{track.rating.toFixed(1)}</div>
              </div>
              <div className="flex items-center gap-3 mt-1.5">
                <EmojiTrackActions
                  track={{ id: track.id, emojis: track.emojis }}
                  onUpdate={handleTrackUpdate}
                  compact
                />
                <span className="text-xs font-mono">
                  <span className="text-green-400">{track.wins}W</span>
                  <span className="text-slate-600 mx-0.5">-</span>
                  <span className="text-red-400">{track.losses}L</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Desktop table view */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('rating')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Rating {getSortIcon('rating')}
                </button>
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('title')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Title {getSortIcon('title')}
                </button>
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">Emojis</th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('artist')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Artist {getSortIcon('artist')}
                </button>
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('wins')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Wins {getSortIcon('wins')}
                </button>
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('losses')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Losses {getSortIcon('losses')}
                </button>
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">
                <button
                  type="button"
                  onClick={() => handleSort('comparison_count')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  Total {getSortIcon('comparison_count')}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedTracks.map((track) => (
              <tr key={track.id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                <td className="py-3 px-2 text-slate-200 font-mono">
                  {track.rating.toFixed(1)}
                </td>
                <td className="py-3 px-2 text-slate-200 max-w-xs truncate" title={track.title}>
                  {track.title}
                </td>
                <td className="py-3 px-2">
                  <EmojiTrackActions
                    track={{ id: track.id, emojis: track.emojis }}
                    onUpdate={handleTrackUpdate}
                    compact
                  />
                </td>
                <td className="py-3 px-2 text-slate-400 max-w-xs truncate" title={track.artist}>
                  {track.artist || 'Unknown Artist'}
                </td>
                <td className="py-3 px-2 text-green-400 font-mono">
                  {track.wins}
                </td>
                <td className="py-3 px-2 text-red-400 font-mono">
                  {track.losses}
                </td>
                <td className="py-3 px-2 text-slate-400 font-mono">
                  {track.comparison_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {tracks.length === 0 && (
        <div className="text-center py-8 text-slate-500">
          No tracks found in this playlist
        </div>
      )}
    </div>
  );
}
