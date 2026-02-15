import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play } from 'lucide-react';
import {
  getStations,
  createStation,
  updateStation,
  deleteStation,
} from '../api/radio';
import type { Station } from '../api/radio';
import { getPlaylistTracks } from '../api/playlists';
import { usePlaylists } from '../hooks/usePlaylists';
import { usePlayer } from '../hooks/usePlayer';
import type { Playlist } from '../types';

interface StationItemProps {
  station: Station;
  onPlay: (station: Station) => void;
  onEdit: (station: Station) => void;
  onDelete: (id: number) => void;
  isDeleting: boolean;
}

function StationItem({
  station,
  onPlay,
  onEdit,
  onDelete,
  isDeleting,
}: StationItemProps): JSX.Element {
  const handleClick = (): void => {
    onPlay(station);
  };

  const handleEdit = (e: React.MouseEvent): void => {
    e.stopPropagation();
    onEdit(station);
  };

  const handleDelete = (e: React.MouseEvent): void => {
    e.stopPropagation();
    if (confirm('Delete station "' + station.name + '"?')) {
      onDelete(station.id);
    }
  };

  return (
    <div
      className="group flex items-center justify-between p-3 cursor-pointer transition-colors border bg-obsidian-surface border-obsidian-border hover:bg-white/5 hover:border-obsidian-accent/30"
      onClick={handleClick}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-medium truncate text-white/90">
            {station.name}
          </p>
          <p className="text-xs text-white/50 font-sf-mono">
            {station.shuffle_enabled ? 'Shuffle' : 'Sequential'}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleEdit}
          className="opacity-0 group-hover:opacity-100 p-1 text-white/50 hover:text-obsidian-accent transition-opacity"
          aria-label="Edit station"
          title="Edit Station"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
        </button>
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="opacity-0 group-hover:opacity-100 p-1 text-white/50 hover:text-rose-400 transition-opacity disabled:opacity-50"
          aria-label="Delete station"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <Play className="h-4 w-4 text-white/50" />
      </div>
    </div>
  );
}

interface CreateStationFormProps {
  onSubmit: (name: string, playlistId: number, shuffleEnabled: boolean) => void;
  onCancel: () => void;
  isCreating: boolean;
  playlists: Playlist[];
  playlistsLoading: boolean;
}

function CreateStationForm({
  onSubmit,
  onCancel,
  isCreating,
  playlists,
  playlistsLoading,
}: CreateStationFormProps): JSX.Element {
  const [name, setName] = useState('');
  const [playlistId, setPlaylistId] = useState<number | undefined>(undefined);
  const [shuffleEnabled, setShuffleEnabled] = useState(true);

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (name.trim() && playlistId) {
      onSubmit(name.trim(), playlistId, shuffleEnabled);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Station name"
        className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white placeholder-white/40 focus:outline-none focus:border-obsidian-accent/50"
        autoFocus
        disabled={isCreating}
      />

      <div className="space-y-1">
        <label className="text-xs text-white/60 font-sf-mono">Playlist</label>
        <select
          value={playlistId ?? ''}
          onChange={(e) => setPlaylistId(e.target.value ? Number(e.target.value) : undefined)}
          className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
          disabled={isCreating || playlistsLoading}
        >
          <option value="">Select playlist</option>
          {playlists.map((playlist) => (
            <option key={playlist.id} value={playlist.id}>
              {playlist.name} ({playlist.track_count} tracks)
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-white/60 font-sf-mono">Mode</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShuffleEnabled(true)}
            className={
              'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
              (shuffleEnabled
                ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                : 'border-obsidian-border text-white/60 hover:bg-white/5')
            }
            disabled={isCreating}
          >
            Shuffle
          </button>
          <button
            type="button"
            onClick={() => setShuffleEnabled(false)}
            className={
              'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
              (!shuffleEnabled
                ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                : 'border-obsidian-border text-white/60 hover:bg-white/5')
            }
            disabled={isCreating}
          >
            Sequential
          </button>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!name.trim() || !playlistId || isCreating}
          className="flex-1 border border-obsidian-accent/30 text-obsidian-accent px-3 py-1.5 text-sm tracking-wider hover:bg-obsidian-accent/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isCreating ? 'Creating...' : 'Create'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isCreating}
          className="px-3 py-1.5 border border-obsidian-border text-white/60 text-sm tracking-wider hover:bg-white/5 disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

interface EditStationModalProps {
  station: Station;
  onSubmit: (updates: { name?: string; playlist_id?: number; shuffle_enabled?: boolean }) => void;
  onClose: () => void;
  isUpdating: boolean;
  playlists: Playlist[];
  playlistsLoading: boolean;
}

function EditStationModal({
  station,
  onSubmit,
  onClose,
  isUpdating,
  playlists,
  playlistsLoading,
}: EditStationModalProps): JSX.Element {
  const [name, setName] = useState(station.name);
  const [playlistId, setPlaylistId] = useState<number>(station.playlist_id);
  const [shuffleEnabled, setShuffleEnabled] = useState(station.shuffle_enabled);

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    const updates: { name?: string; playlist_id?: number; shuffle_enabled?: boolean } = {};
    if (name.trim() !== station.name) updates.name = name.trim();
    if (playlistId !== station.playlist_id) updates.playlist_id = playlistId;
    if (shuffleEnabled !== station.shuffle_enabled) updates.shuffle_enabled = shuffleEnabled;

    if (Object.keys(updates).length > 0) {
      onSubmit(updates);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-obsidian-surface p-6 w-full max-w-md mx-4 border border-obsidian-accent/30"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-white/90 mb-4">Edit Station</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs text-white/60 font-sf-mono">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Station name"
              className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white placeholder-white/40 focus:outline-none focus:border-obsidian-accent/50"
              autoFocus
              disabled={isUpdating}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-white/60 font-sf-mono">Playlist</label>
            <select
              value={playlistId}
              onChange={(e) => setPlaylistId(Number(e.target.value))}
              className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
              disabled={isUpdating || playlistsLoading}
            >
              {playlists.map((playlist) => (
                <option key={playlist.id} value={playlist.id}>
                  {playlist.name} ({playlist.track_count} tracks)
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-white/60 font-sf-mono">Mode</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShuffleEnabled(true)}
                className={
                  'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
                  (shuffleEnabled
                    ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                    : 'border-obsidian-border text-white/60 hover:bg-white/5')
                }
                disabled={isUpdating}
              >
                Shuffle
              </button>
              <button
                type="button"
                onClick={() => setShuffleEnabled(false)}
                className={
                  'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
                  (!shuffleEnabled
                    ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                    : 'border-obsidian-border text-white/60 hover:bg-white/5')
                }
                disabled={isUpdating}
              >
                Sequential
              </button>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={!name.trim() || isUpdating}
              className="flex-1 border border-obsidian-accent/30 text-obsidian-accent px-3 py-2 text-sm tracking-wider hover:bg-obsidian-accent/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isUpdating ? 'Saving...' : 'Save'}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={isUpdating}
              className="px-4 py-2 border border-obsidian-border text-white/60 text-sm tracking-wider hover:bg-white/5 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function StationsList(): JSX.Element {
  const [isCreating, setIsCreating] = useState(false);
  const [editingStation, setEditingStation] = useState<Station | null>(null);
  const queryClient = useQueryClient();
  const { play } = usePlayer();

  const { data: stations, isLoading, error } = useQuery<Station[]>({
    queryKey: ['stations'],
    queryFn: getStations,
  });

  const { data: playlists, isLoading: playlistsLoading } = usePlaylists();

  const handlePlayStation = async (station: Station): Promise<void> => {
    try {
      // Fetch playlist tracks
      const playlistData = await getPlaylistTracks(station.playlist_id);

      if (playlistData.tracks && playlistData.tracks.length > 0) {
        // Play first track with playlist context
        const firstTrack = playlistData.tracks[0];
        // Convert PlaylistTrackEntry to Track (fill in required fields)
        const track = {
          ...firstTrack,
          artist: firstTrack.artist ?? 'Unknown Artist',
        };
        await play(track, {
          type: 'playlist',
          playlist_id: station.playlist_id,
          start_index: 0,
          shuffle: station.shuffle_enabled,
        });
      }
    } catch (error) {
      console.error('Failed to play station:', error);
    }
  };

  const createMutation = useMutation({
    mutationFn: ({ name, playlistId, shuffleEnabled }: { name: string; playlistId: number; shuffleEnabled: boolean }) =>
      createStation(name, playlistId, shuffleEnabled ? 'shuffle' : 'queue', 'all'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      setIsCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ stationId, updates }: { stationId: number; updates: { name?: string; playlist_id?: number; shuffle_enabled?: boolean } }) => {
      const apiUpdates: { name?: string; playlist_id?: number; mode?: 'shuffle' | 'queue' } = {};
      if (updates.name) apiUpdates.name = updates.name;
      if (updates.playlist_id) apiUpdates.playlist_id = updates.playlist_id;
      if (updates.shuffle_enabled !== undefined) {
        apiUpdates.mode = updates.shuffle_enabled ? 'shuffle' : 'queue';
      }
      return updateStation(stationId, apiUpdates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      setEditingStation(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteStation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
    },
  });

  if (isLoading) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border p-4 animate-pulse">
        <div className="h-4 bg-obsidian-border w-20 mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-obsidian-border" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border p-4">
        <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider mb-3 font-sf-mono">
          Stations
        </h3>
        <p className="text-rose-400 text-sm font-sf-mono">Failed to load stations</p>
      </div>
    );
  }

  return (
    <>
      <div className="bg-obsidian-surface border border-obsidian-border p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider font-sf-mono">
            Stations
          </h3>
          {!isCreating && (
            <button
              onClick={() => setIsCreating(true)}
              className="text-xs text-obsidian-accent hover:text-obsidian-accent/80 font-medium font-sf-mono transition-colors"
            >
              + Add
            </button>
          )}
        </div>

        {isCreating && (
          <div className="mb-4">
            <CreateStationForm
              onSubmit={(name, playlistId, shuffleEnabled) =>
                createMutation.mutate({ name, playlistId, shuffleEnabled })
              }
              onCancel={() => setIsCreating(false)}
              isCreating={createMutation.isPending}
              playlists={playlists ?? []}
              playlistsLoading={playlistsLoading}
            />
          </div>
        )}

        {!stations || stations.length === 0 ? (
          <p className="text-white/40 text-sm font-sf-mono">No stations created</p>
        ) : (
          <div className="space-y-2">
            {stations.map((station) => (
              <StationItem
                key={station.id}
                station={station}
                onPlay={handlePlayStation}
                onEdit={(s) => setEditingStation(s)}
                onDelete={(id) => deleteMutation.mutate(id)}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {editingStation && (
        <EditStationModal
          station={editingStation}
          onSubmit={(updates) => updateMutation.mutate({ stationId: editingStation.id, updates })}
          onClose={() => setEditingStation(null)}
          isUpdating={updateMutation.isPending}
          playlists={playlists ?? []}
          playlistsLoading={playlistsLoading}
        />
      )}
    </>
  );
}
