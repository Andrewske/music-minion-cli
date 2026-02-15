import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getStations,
  activateStation,
  deactivateStation,
  createStation,
  updateStation,
  deleteStation,
} from '../api/radio';
import type { Station, SourceFilter } from '../api/radio';
import { ScheduleEditorModal } from './ScheduleEditorModal';
import { usePlaylists } from '../hooks/usePlaylists';
import type { Playlist } from '../types';

interface StationItemProps {
  station: Station;
  onActivate: (id: number) => void;
  onDeactivate: () => void;
  onEdit: (station: Station) => void;
  onDelete: (id: number) => void;
  onEditSchedule?: (id: number, name: string) => void;
  isActivating: boolean;
  isDeleting: boolean;
}

function StationItem({
  station,
  onActivate,
  onDeactivate,
  onEdit,
  onDelete,
  onEditSchedule,
  isActivating,
  isDeleting,
}: StationItemProps): JSX.Element {
  const handleClick = (): void => {
    if (isActivating) return; // Prevent double-clicks while activating
    if (station.is_active) {
      onDeactivate();
    } else {
      onActivate(station.id);
    }
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

  const handleEditSchedule = (e: React.MouseEvent): void => {
    e.stopPropagation();
    onEditSchedule?.(station.id, station.name);
  };

  const isMetaStation = station.playlist_id === null;

  return (
    <div
      className={
        'group flex items-center justify-between p-3 cursor-pointer transition-colors border ' +
        (station.is_active
          ? 'bg-obsidian-accent/10 border-obsidian-accent/30'
          : 'bg-obsidian-surface border-obsidian-border hover:bg-white/5 hover:border-obsidian-accent/30')
      }
      onClick={handleClick}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={
            'w-2 h-2 rounded-full shrink-0 ' +
            (station.is_active ? 'bg-obsidian-accent animate-pulse' : 'bg-white/30')
          }
        />
        <div className="min-w-0">
          <p
            className={
              'text-sm font-medium truncate ' +
              (station.is_active ? 'text-obsidian-accent' : 'text-white/90')
            }
          >
            {station.name}
          </p>
          <p className="text-xs text-white/50 font-sf-mono capitalize">
            {station.mode}
            {station.source_filter !== 'all' && (
              <span className="ml-1 text-white/40">• {station.source_filter}</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {station.is_active && (
          <span className="text-xs text-obsidian-accent font-medium font-sf-mono">LIVE</span>
        )}
        {isMetaStation && onEditSchedule && (
          <button
            onClick={handleEditSchedule}
            className="opacity-0 group-hover:opacity-100 p-1 text-white/50 hover:text-obsidian-accent transition-opacity"
            aria-label="Edit schedule"
            title="Edit Schedule"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </button>
        )}
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
      </div>
    </div>
  );
}

interface CreateStationFormProps {
  onSubmit: (name: string, playlistId?: number, mode?: 'shuffle' | 'queue', sourceFilter?: SourceFilter) => void;
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
  const [mode, setMode] = useState<'shuffle' | 'queue'>('shuffle');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (name.trim()) {
      onSubmit(name.trim(), playlistId, mode, sourceFilter);
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
        <label className="text-xs text-white/60 font-sf-mono">Playlist (optional)</label>
        <select
          value={playlistId ?? ''}
          onChange={(e) => setPlaylistId(e.target.value ? Number(e.target.value) : undefined)}
          className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
          disabled={isCreating || playlistsLoading}
        >
          <option value="">Meta-station (no playlist)</option>
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
            onClick={() => setMode('shuffle')}
            className={
              'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
              (mode === 'shuffle'
                ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                : 'border-obsidian-border text-white/60 hover:bg-white/5')
            }
            disabled={isCreating}
          >
            Shuffle
          </button>
          <button
            type="button"
            onClick={() => setMode('queue')}
            className={
              'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
              (mode === 'queue'
                ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                : 'border-obsidian-border text-white/60 hover:bg-white/5')
            }
            disabled={isCreating}
          >
            Queue
          </button>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-white/60 font-sf-mono">Source Filter</label>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
          className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
          disabled={isCreating}
        >
          <option value="all">All Sources</option>
          <option value="local">Local Files Only</option>
          <option value="youtube">YouTube Only</option>
          <option value="soundcloud">SoundCloud Only</option>
          <option value="spotify">Spotify Only</option>
        </select>
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!name.trim() || isCreating}
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
  onSubmit: (updates: { name?: string; playlist_id?: number | null; mode?: 'shuffle' | 'queue'; source_filter?: SourceFilter }) => void;
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
  const [playlistId, setPlaylistId] = useState<number | null>(station.playlist_id);
  const [mode, setMode] = useState<'shuffle' | 'queue'>(station.mode);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>(station.source_filter);

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    const updates: { name?: string; playlist_id?: number | null; mode?: 'shuffle' | 'queue'; source_filter?: SourceFilter } = {};
    if (name.trim() !== station.name) updates.name = name.trim();
    if (playlistId !== station.playlist_id) updates.playlist_id = playlistId;
    if (mode !== station.mode) updates.mode = mode;
    if (sourceFilter !== station.source_filter) updates.source_filter = sourceFilter;

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
              value={playlistId ?? ''}
              onChange={(e) => setPlaylistId(e.target.value ? Number(e.target.value) : null)}
              className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
              disabled={isUpdating || playlistsLoading}
            >
              <option value="">Meta-station (no playlist)</option>
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
                onClick={() => setMode('shuffle')}
                className={
                  'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
                  (mode === 'shuffle'
                    ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                    : 'border-obsidian-border text-white/60 hover:bg-white/5')
                }
                disabled={isUpdating}
              >
                Shuffle
              </button>
              <button
                type="button"
                onClick={() => setMode('queue')}
                className={
                  'flex-1 px-3 py-1.5 text-sm tracking-wider transition-colors border ' +
                  (mode === 'queue'
                    ? 'border-obsidian-accent text-obsidian-accent bg-obsidian-accent/10'
                    : 'border-obsidian-border text-white/60 hover:bg-white/5')
                }
                disabled={isUpdating}
              >
                Queue
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-white/60 font-sf-mono">Source Filter</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
              className="w-full bg-transparent border border-obsidian-border px-3 py-2 text-sm text-white focus:outline-none focus:border-obsidian-accent/50"
              disabled={isUpdating}
            >
              <option value="all">All Sources</option>
              <option value="local">Local Files Only</option>
              <option value="youtube">YouTube Only</option>
              <option value="soundcloud">SoundCloud Only</option>
              <option value="spotify">Spotify Only</option>
            </select>
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
  const [editingSchedule, setEditingSchedule] = useState<{
    stationId: number;
    stationName: string;
  } | null>(null);
  const queryClient = useQueryClient();

  const { data: stations, isLoading, error } = useQuery<Station[]>({
    queryKey: ['stations'],
    queryFn: getStations,
  });

  const { data: playlists, isLoading: playlistsLoading } = usePlaylists();

  const activateMutation = useMutation({
    mutationFn: activateStation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      queryClient.invalidateQueries({ queryKey: ['nowPlaying'] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateStation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      queryClient.invalidateQueries({ queryKey: ['nowPlaying'] });
    },
  });

  const createMutation = useMutation({
    mutationFn: ({ name, playlistId, mode, sourceFilter }: { name: string; playlistId?: number; mode?: 'shuffle' | 'queue'; sourceFilter?: SourceFilter }) =>
      createStation(name, playlistId, mode, sourceFilter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      setIsCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ stationId, updates }: { stationId: number; updates: { name?: string; playlist_id?: number | null; mode?: 'shuffle' | 'queue'; source_filter?: SourceFilter } }) =>
      updateStation(stationId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      queryClient.invalidateQueries({ queryKey: ['nowPlaying'] });
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
              onSubmit={(name, playlistId, mode, sourceFilter) => createMutation.mutate({ name, playlistId, mode, sourceFilter })}
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
                onActivate={(id) => activateMutation.mutate(id)}
                onDeactivate={() => deactivateMutation.mutate()}
                onEdit={(s) => setEditingStation(s)}
                onDelete={(id) => deleteMutation.mutate(id)}
                onEditSchedule={(id, name) => setEditingSchedule({ stationId: id, stationName: name })}
                isActivating={activateMutation.isPending}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {editingSchedule && (
        <ScheduleEditorModal
          isOpen={true}
          onClose={() => setEditingSchedule(null)}
          stationId={editingSchedule.stationId}
          stationName={editingSchedule.stationName}
        />
      )}

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
