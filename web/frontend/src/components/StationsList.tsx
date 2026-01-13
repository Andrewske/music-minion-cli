import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getStations,
  activateStation,
  deactivateStation,
  createStation,
  deleteStation,
} from '../api/radio';
import type { Station } from '../api/radio';

interface StationItemProps {
  station: Station;
  onActivate: (id: number) => void;
  onDeactivate: () => void;
  onDelete: (id: number) => void;
  isActivating: boolean;
  isDeleting: boolean;
}

function StationItem({
  station,
  onActivate,
  onDeactivate,
  onDelete,
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

  const handleDelete = (e: React.MouseEvent): void => {
    e.stopPropagation();
    if (confirm('Delete station "' + station.name + '"?')) {
      onDelete(station.id);
    }
  };

  return (
    <div
      className={
        'group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ' +
        (station.is_active
          ? 'bg-emerald-500/20 border border-emerald-500/30'
          : 'bg-slate-800/50 hover:bg-slate-800 border border-transparent')
      }
      onClick={handleClick}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={
            'w-2 h-2 rounded-full shrink-0 ' +
            (station.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600')
          }
        />
        <div className="min-w-0">
          <p
            className={
              'text-sm font-medium truncate ' +
              (station.is_active ? 'text-emerald-400' : 'text-slate-200')
            }
          >
            {station.name}
          </p>
          <p className="text-xs text-slate-500 capitalize">{station.mode}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {station.is_active && (
          <span className="text-xs text-emerald-500 font-medium">LIVE</span>
        )}
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-opacity disabled:opacity-50"
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
  onSubmit: (name: string) => void;
  onCancel: () => void;
  isCreating: boolean;
}

function CreateStationForm({
  onSubmit,
  onCancel,
  isCreating,
}: CreateStationFormProps): JSX.Element {
  const [name, setName] = useState('');

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (name.trim()) {
      onSubmit(name.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Station name"
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        autoFocus
        disabled={isCreating}
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!name.trim() || isCreating}
          className="flex-1 bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isCreating ? 'Creating...' : 'Create'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isCreating}
          className="px-3 py-1.5 bg-slate-800 text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export function StationsList(): JSX.Element {
  const [isCreating, setIsCreating] = useState(false);
  const queryClient = useQueryClient();

  const { data: stations, isLoading, error } = useQuery<Station[]>({
    queryKey: ['stations'],
    queryFn: getStations,
  });

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
    mutationFn: (name: string) => createStation(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] });
      setIsCreating(false);
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
      <div className="bg-slate-900 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-slate-800 rounded w-20 mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-slate-800 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Stations
        </h3>
        <p className="text-red-400 text-sm">Failed to load stations</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Stations
        </h3>
        {!isCreating && (
          <button
            onClick={() => setIsCreating(true)}
            className="text-xs text-emerald-500 hover:text-emerald-400 font-medium transition-colors"
          >
            + Add
          </button>
        )}
      </div>

      {isCreating && (
        <div className="mb-4">
          <CreateStationForm
            onSubmit={(name) => createMutation.mutate(name)}
            onCancel={() => setIsCreating(false)}
            isCreating={createMutation.isPending}
          />
        </div>
      )}

      {!stations || stations.length === 0 ? (
        <p className="text-slate-500 text-sm">No stations created</p>
      ) : (
        <div className="space-y-2">
          {stations.map((station) => (
            <StationItem
              key={station.id}
              station={station}
              onActivate={(id) => activateMutation.mutate(id)}
              onDeactivate={() => deactivateMutation.mutate()}
              onDelete={(id) => deleteMutation.mutate(id)}
              isActivating={activateMutation.isPending}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}
