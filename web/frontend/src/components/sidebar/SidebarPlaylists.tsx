import { Link, useParams } from '@tanstack/react-router';
import { ListMusic } from 'lucide-react';
import { usePlaylists } from '../../hooks/usePlaylists';
import { SidebarSection } from './SidebarSection';

interface SidebarPlaylistsProps {
  sidebarExpanded: boolean;
}

export function SidebarPlaylists({ sidebarExpanded }: SidebarPlaylistsProps): JSX.Element {
  const { data: playlists, isLoading } = usePlaylists();
  const params = useParams({ strict: false });
  const activePlaylistId = params.playlistId ? parseInt(params.playlistId, 10) : null;

  return (
    <SidebarSection title="Playlists" sidebarExpanded={sidebarExpanded}>
      <div className="space-y-0.5">
        {isLoading && (
          <div className="px-3 py-2 text-white/30 text-sm">Loading...</div>
        )}
        {playlists?.map(playlist => {
          const isActive = playlist.id === activePlaylistId;
          return (
            <Link
              key={playlist.id}
              to="/playlist-builder/$playlistId"
              params={{ playlistId: String(playlist.id) }}
              className={`flex items-center gap-2 px-3 py-2 rounded transition-colors
                ${isActive
                  ? 'bg-obsidian-accent/10 text-obsidian-accent border-l-2 border-l-obsidian-accent'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <ListMusic className="w-4 h-4 flex-shrink-0" />
              <span className="truncate text-sm">{playlist.name}</span>
              <span className="ml-auto text-xs text-white/40">
                {playlist.track_count}
              </span>
            </Link>
          );
        })}
      </div>
    </SidebarSection>
  );
}
