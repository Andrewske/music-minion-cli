/**
 * Track search autocomplete for fixing low-confidence matches.
 * Debounced search (300ms) with dropdown results.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { searchTracks, type TrackSearchResult } from '../../api/soundcloud';

export interface TrackSearchAutocompleteProps {
  onSelect: (track: { id: number; title: string; artist: string }) => void;
  onCancel: () => void;
  initialQuery?: string;
}

export function TrackSearchAutocomplete({
  onSelect,
  onCancel,
  initialQuery = '',
}: TrackSearchAutocompleteProps): JSX.Element {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<TrackSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Debounced search
  const performSearch = useCallback(async (searchQuery: string) => {
    if (searchQuery.trim().length < 2) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const tracks = await searchTracks(searchQuery, 10);
      setResults(tracks);
      setSelectedIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle query changes with debounce
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query, performSearch]);

  const handleSelect = (track: TrackSearchResult): void => {
    onSelect({
      id: track.id,
      title: track.title,
      artist: track.artist || '',
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (results[selectedIndex]) {
          handleSelect(results[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        onCancel();
        break;
    }
  };

  return (
    <div className="relative w-full">
      {/* Search input */}
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search for a track..."
          className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
        />
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Results dropdown */}
      {(results.length > 0 || isLoading || error) && (
        <div className="absolute z-50 mt-1 w-full bg-slate-800 border border-slate-600 rounded shadow-lg max-h-60 overflow-y-auto">
          {isLoading && (
            <div className="px-3 py-2 text-slate-400 text-sm">Searching...</div>
          )}

          {error && (
            <div className="px-3 py-2 text-red-400 text-sm">{error}</div>
          )}

          {!isLoading && !error && results.length === 0 && query.trim().length >= 2 && (
            <div className="px-3 py-2 text-slate-400 text-sm">No tracks found</div>
          )}

          {results.map((track, index) => (
            <button
              key={track.id}
              type="button"
              onClick={() => handleSelect(track)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                index === selectedIndex
                  ? 'bg-orange-500/20 text-white'
                  : 'text-slate-300 hover:bg-slate-700'
              }`}
            >
              <div className="font-medium truncate">{track.title}</div>
              {track.artist && (
                <div className="text-xs text-slate-400 truncate">{track.artist}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
