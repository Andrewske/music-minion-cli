import { useLocation, useNavigate, useParams } from '@tanstack/react-router';
import { ListMusic, Pin } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { getPlaylistTracks, pinPlaylist, unpinPlaylist, reorderPinnedPlaylist } from '../../api/playlists';
import { usePlaylists } from '../../hooks/usePlaylists';
import { usePlayerStore } from '../../stores/playerStore';
import { SidebarSection } from './SidebarSection';
import type { Playlist } from '../../types';

interface SidebarPlaylistsProps {
  sidebarExpanded: boolean;
}

export function SidebarPlaylists({ sidebarExpanded }: SidebarPlaylistsProps): JSX.Element {
  const { data: playlists, isLoading } = usePlaylists();
  const params = useParams({ strict: false });
  const activePlaylistId = params.playlistId ? parseInt(params.playlistId, 10) : null;
  const location = useLocation();
  const navigate = useNavigate();
  const play = usePlayerStore((s) => s.play);

  const isOnHome = location.pathname === '/';

  const queryClient = useQueryClient();
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  const pinMutation = useMutation({
    mutationFn: pinPlaylist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
  });

  const unpinMutation = useMutation({
    mutationFn: unpinPlaylist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
  });

  const reorderMutation = useMutation({
    mutationFn: ({ id, position }: { id: number; position: number }) =>
      reorderPinnedPlaylist(id, position),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
  });

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const pinnedPlaylists = playlists?.filter(p => p.pin_order !== null) ?? [];
  const unpinnedPlaylists = playlists?.filter(p => p.pin_order === null) ?? [];

  const handlePlaylistClick = async (playlistId: number): Promise<void> => {
    if (isOnHome) {
      // Play the playlist directly
      const { tracks } = await getPlaylistTracks(playlistId);
      if (tracks.length > 0) {
        const firstTrack = tracks[0];
        // Convert PlaylistTrackEntry to Track (fill in required fields)
        const track = {
          ...firstTrack,
          artist: firstTrack.artist ?? 'Unknown Artist',
        };
        play(track, { type: 'playlist', playlist_id: playlistId });
      }
    } else {
      // Navigate to builder
      navigate({ to: '/playlist-builder/$playlistId', params: { playlistId: String(playlistId) } });
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const newIndex = pinnedPlaylists.findIndex(p => p.id === over.id);
      reorderMutation.mutate({ id: active.id as number, position: newIndex + 1 });
    }
  };

  const SortablePlaylistItem = ({ playlist }: { playlist: Playlist }) => {
    const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
      id: playlist.id,
    });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
    };

    return (
      <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
        <PlaylistItem playlist={playlist} isPinned />
      </div>
    );
  };

  const PlaylistItem = ({ playlist, isPinned }: { playlist: Playlist; isPinned: boolean }) => {
    const isActive = playlist.id === activePlaylistId;
    const isHovered = hoveredId === playlist.id;

    const handlePinToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (isPinned) {
        unpinMutation.mutate(playlist.id);
      } else {
        pinMutation.mutate(playlist.id);
      }
    };

    return (
      <button
        key={playlist.id}
        type="button"
        onClick={() => handlePlaylistClick(playlist.id)}
        onMouseEnter={() => setHoveredId(playlist.id)}
        onMouseLeave={() => setHoveredId(null)}
        className={`w-full flex items-center gap-2 px-3 py-2 rounded transition-colors text-left group
          ${isActive
            ? 'bg-obsidian-accent/10 text-obsidian-accent border-l-2 border-l-obsidian-accent'
            : 'text-white/60 hover:text-white hover:bg-white/5'
          }`}
      >
        <ListMusic className="w-4 h-4 flex-shrink-0" />
        {isPinned && <Pin className="w-3 h-3 flex-shrink-0 text-obsidian-accent" />}
        <span className="truncate text-sm">{playlist.name}</span>
        <span className="ml-auto text-xs text-white/40 flex items-center gap-1">
          {isHovered && (
            <button
              type="button"
              onClick={handlePinToggle}
              className="p-0.5 hover:bg-white/10 rounded"
              title={isPinned ? 'Unpin' : 'Pin to top'}
            >
              <Pin className={`w-3 h-3 ${isPinned ? 'text-obsidian-accent' : 'text-white/40'}`} />
            </button>
          )}
          {playlist.track_count}
        </span>
      </button>
    );
  };

  return (
    <SidebarSection title="Playlists" sidebarExpanded={sidebarExpanded}>
      <div className="space-y-0.5">
        {isLoading && (
          <div className="px-3 py-2 text-white/30 text-sm">Loading...</div>
        )}
        {pinnedPlaylists.length > 0 && (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={pinnedPlaylists.map(p => p.id)} strategy={verticalListSortingStrategy}>
              {pinnedPlaylists.map(playlist => (
                <SortablePlaylistItem key={playlist.id} playlist={playlist} />
              ))}
            </SortableContext>
          </DndContext>
        )}
        {unpinnedPlaylists.map(playlist => (
          <PlaylistItem key={playlist.id} playlist={playlist} isPinned={false} />
        ))}
      </div>
    </SidebarSection>
  );
}
