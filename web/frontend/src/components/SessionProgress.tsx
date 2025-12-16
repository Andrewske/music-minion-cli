
import { useState, useEffect, useRef } from 'react';
import type { FoldersResponse, Playlist } from '../types';

interface SessionProgressProps {
  completed: number;
  priorityPath?: string;
  onPriorityChange?: (newPriorityPath: string | null) => void;
  folders?: FoldersResponse;
  rankingMode?: 'global' | 'playlist';
  playlists?: Playlist[];
  selectedPlaylistId?: number | null;
  onPlaylistChange?: (playlistId: number | null) => void;
}

export function SessionProgress({
  completed,
  priorityPath,
  onPriorityChange,
  folders: foldersData,
  rankingMode = 'global',
  playlists = [],
  selectedPlaylistId,
  onPlaylistChange
}: SessionProgressProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Use passed folders or default to empty array
  const folders = foldersData?.folders || [];

  // Determine current display text and dropdown options based on mode
  const currentFolderName = priorityPath?.split('/').filter(Boolean).pop() ||
    (folders.includes('2025') ? '2025' : 'All');

  const selectedPlaylist = playlists.find(p => p.id === selectedPlaylistId);
  const currentDisplayText = rankingMode === 'playlist'
    ? (selectedPlaylist?.name || 'Select Playlist')
    : currentFolderName;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleFolderSelect = (folderName: string) => {
    const newPriorityPath = folderName === '2025' || folderName === 'All' ? null : `${foldersData?.root || '/music'}/${folderName}`;
    onPriorityChange?.(newPriorityPath);
    setIsOpen(false);
  };

  const handlePlaylistSelect = (playlistId: number | null) => {
    onPlaylistChange?.(playlistId);
    setIsOpen(false);
  };

  return (
    <div className="w-full">
      <div className="flex items-center gap-2">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="text-emerald-400 font-mono truncate max-w-[200px] hover:text-emerald-300 transition-colors flex items-center gap-1"
            title={rankingMode === 'playlist' ? `Selected playlist: ${currentDisplayText}` : `Priority folder: ${currentDisplayText}`}
          >
            {currentDisplayText}
            <span className={`text-xs transition-transform ${isOpen ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>

          {isOpen && (
            <div className="absolute top-full left-0 mt-1 bg-slate-800 border border-slate-600 rounded-md shadow-lg z-10 min-w-[200px] max-h-48 overflow-y-auto">
              {rankingMode === 'playlist' ? (
                // Playlist dropdown
                <>
                  <button
                    type="button"
                    onClick={() => handlePlaylistSelect(null)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 transition-colors ${
                      !selectedPlaylistId ? 'text-emerald-400 bg-slate-700' : 'text-slate-200'
                    }`}
                  >
                    Select Playlist...
                  </button>
                  {playlists.map((playlist) => (
                    <button
                      type="button"
                      key={playlist.id}
                      onClick={() => handlePlaylistSelect(playlist.id)}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 transition-colors ${
                        playlist.id === selectedPlaylistId ? 'text-emerald-400 bg-slate-700' : 'text-slate-200'
                      }`}
                    >
                      {playlist.name} ({playlist.track_count} tracks)
                    </button>
                  ))}
                </>
              ) : (
                // Folder dropdown
                folders.map((folder) => (
                  <button
                    type="button"
                    key={folder}
                    onClick={() => handleFolderSelect(folder)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 transition-colors ${
                      folder === currentFolderName ? 'text-emerald-400 bg-slate-700' : 'text-slate-200'
                    }`}
                  >
                    {folder}
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        <span className="text-slate-200 font-bold">+{completed}</span>
      </div>
    </div>
  );
}
