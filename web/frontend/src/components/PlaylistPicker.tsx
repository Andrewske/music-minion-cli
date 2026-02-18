import type { Playlist } from '../types';

interface PlaylistPickerProps {
  playlists: Playlist[];
  selectedPlaylistId: number | null;
  onSelect: (playlistId: number) => void;
  isLoading?: boolean;
}

export function PlaylistPicker({
  playlists,
  selectedPlaylistId,
  onSelect,
  isLoading = false,
}: PlaylistPickerProps): JSX.Element {
  if (isLoading) {
    return (
      <div className="text-white/40 text-sm py-4 font-sf-mono">Loading...</div>
    );
  }

  if (playlists.length === 0) {
    return (
      <p className="text-white/30 text-sm py-4">No playlists found</p>
    );
  }

  return (
    <div className="space-y-px">
      {playlists.map((playlist) => {
        const isSelected = playlist.id === selectedPlaylistId;

        return (
          <div
            key={playlist.id}
            className={`group border-b transition-colors ${
              isSelected
                ? 'border-obsidian-accent bg-obsidian-accent/10'
                : 'border-obsidian-border hover:border-obsidian-accent/50'
            }`}
          >
            <button
              onClick={() => onSelect(playlist.id)}
              disabled={isLoading}
              className="w-full flex items-center justify-between py-4 text-left disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`transition-colors ${
                    isSelected
                      ? 'text-obsidian-accent'
                      : 'text-white/90 group-hover:text-obsidian-accent'
                  }`}
                >
                  {playlist.name}
                </span>
                {playlist.type === 'smart' && (
                  <span className="text-[10px] text-obsidian-accent/60 tracking-wider uppercase">
                    Smart
                  </span>
                )}
              </div>
              <span className="text-white/20 text-sm font-sf-mono">
                {playlist.track_count}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
