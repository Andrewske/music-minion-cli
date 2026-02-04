import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSchedule,
  getStations,
  createScheduleEntry,
  updateScheduleEntry,
  deleteScheduleEntry,
  reorderSchedule,
} from '../api/radio';
import type { ScheduleEntry, Station } from '../api/radio';
import { TimeInput } from './TimeInput';

interface ScheduleEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  stationId: number;
  stationName: string;
}

interface ScheduleEntryFormProps {
  stations: Station[];
  currentStationId: number;
  onSubmit: (startTime: string, endTime: string, targetStationId: number) => void;
  isPending: boolean;
  editingEntry?: ScheduleEntry | null;
  onCancelEdit?: () => void;
}

function ScheduleEntryForm({
  stations,
  currentStationId,
  onSubmit,
  isPending,
  editingEntry,
  onCancelEdit,
}: ScheduleEntryFormProps): JSX.Element {
  const [startTime, setStartTime] = useState(editingEntry?.start_time || '');
  const [endTime, setEndTime] = useState(editingEntry?.end_time || '');
  const [targetStationId, setTargetStationId] = useState<number>(
    editingEntry?.target_station_id || 0
  );
  const [error, setError] = useState('');

  // Update form when editingEntry changes
  useEffect(() => {
    if (editingEntry) {
      setStartTime(editingEntry.start_time);
      setEndTime(editingEntry.end_time);
      setTargetStationId(editingEntry.target_station_id);
    }
  }, [editingEntry]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!startTime || !endTime) {
      setError('Please enter both start and end times');
      return;
    }

    if (!targetStationId) {
      setError('Please select a target station');
      return;
    }

    if (startTime === endTime) {
      setError('Start and end times cannot be the same');
      return;
    }

    onSubmit(startTime, endTime, targetStationId);

    // Reset form if not editing
    if (!editingEntry) {
      setStartTime('');
      setEndTime('');
      setTargetStationId(0);
    }
  };

  const handleCancel = () => {
    setStartTime('');
    setEndTime('');
    setTargetStationId(0);
    setError('');
    onCancelEdit?.();
  };

  // Filter out current station from target options
  const availableStations = stations.filter((s) => s.id !== currentStationId);

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-emerald-500 uppercase tracking-wider mb-4">
        {editingEntry ? 'Edit Entry' : 'Add Time Range'}
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <TimeInput
          label="Start Time"
          value={startTime}
          onChange={setStartTime}
          error={error && !startTime ? 'Required' : ''}
        />

        <TimeInput
          label="End Time"
          value={endTime}
          onChange={setEndTime}
          error={error && !endTime ? 'Required' : ''}
        />

        <div className="flex flex-col">
          <label className="text-sm text-slate-400 mb-1 font-medium">Target Station</label>
          <select
            value={targetStationId}
            onChange={(e) => setTargetStationId(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value={0}>Select station...</option>
            {availableStations.map((station) => (
              <option key={station.id} value={station.id}>
                {station.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="text-sm text-red-400 mb-3">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isPending}
          className="flex-1 bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? 'Saving...' : editingEntry ? 'Update' : 'Add Entry'}
        </button>
        {editingEntry && (
          <button
            type="button"
            onClick={handleCancel}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

interface ScheduleEntryItemProps {
  entry: ScheduleEntry;
  stations: Station[];
  onMoveUp: () => void;
  onMoveDown: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isFirst: boolean;
  isLast: boolean;
  isDeleting: boolean;
}

function ScheduleEntryItem({
  entry,
  stations,
  onMoveUp,
  onMoveDown,
  onEdit,
  onDelete,
  isFirst,
  isLast,
  isDeleting,
}: ScheduleEntryItemProps): JSX.Element {
  const targetStation = stations.find((s) => s.id === entry.target_station_id);
  const isOvernight = entry.start_time > entry.end_time;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex items-center gap-3">
      {/* Position badge */}
      <div className="flex-shrink-0 w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center text-xs font-bold text-slate-400">
        {entry.position + 1}
      </div>

      {/* Time range */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-slate-200 font-medium">
            {entry.start_time} → {entry.end_time}
          </span>
          {isOvernight && (
            <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded">
              Overnight
            </span>
          )}
        </div>
        <div className="text-sm text-slate-400">
          → {targetStation?.name || 'Unknown Station'}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Reorder buttons */}
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={isFirst}
            className="w-6 h-6 flex items-center justify-center bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded text-slate-400 hover:text-slate-200 transition-colors"
            title="Move up"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={isLast}
            className="w-6 h-6 flex items-center justify-center bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded text-slate-400 hover:text-slate-200 transition-colors"
            title="Move down"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Edit button */}
        <button
          type="button"
          onClick={onEdit}
          className="w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-slate-700 rounded text-slate-400 hover:text-emerald-400 transition-colors"
          title="Edit"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
        </button>

        {/* Delete button */}
        <button
          type="button"
          onClick={onDelete}
          disabled={isDeleting}
          className="w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-red-900 rounded text-slate-400 hover:text-red-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Delete"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function ScheduleEditorModal({
  isOpen,
  onClose,
  stationId,
  stationName,
}: ScheduleEditorModalProps): JSX.Element | null {
  const queryClient = useQueryClient();
  const [editingEntry, setEditingEntry] = useState<ScheduleEntry | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Fetch schedule entries
  const { data: schedule, isLoading: isLoadingSchedule } = useQuery({
    queryKey: ['schedule', stationId],
    queryFn: () => getSchedule(stationId),
    enabled: isOpen,
  });

  // Fetch all stations for target selection
  const { data: stations, isLoading: isLoadingStations } = useQuery({
    queryKey: ['stations'],
    queryFn: getStations,
    enabled: isOpen,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: ({
      startTime,
      endTime,
      targetStationId,
    }: {
      startTime: string;
      endTime: string;
      targetStationId: number;
    }) => createScheduleEntry(stationId, startTime, endTime, targetStationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule', stationId] });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({
      entryId,
      startTime,
      endTime,
      targetStationId,
    }: {
      entryId: number;
      startTime: string;
      endTime: string;
      targetStationId: number;
    }) =>
      updateScheduleEntry(entryId, {
        start_time: startTime,
        end_time: endTime,
        target_station_id: targetStationId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule', stationId] });
      setEditingEntry(null);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (entryId: number) => deleteScheduleEntry(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule', stationId] });
      setDeletingId(null);
    },
  });

  // Reorder mutation
  const reorderMutation = useMutation({
    mutationFn: (entryIds: number[]) => reorderSchedule(stationId, entryIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule', stationId] });
    },
  });

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (editingEntry) {
          setEditingEntry(null);
        } else {
          onClose();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose, editingEntry]);

  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  const handleSubmit = (startTime: string, endTime: string, targetStationId: number) => {
    if (editingEntry) {
      updateMutation.mutate({
        entryId: editingEntry.id,
        startTime,
        endTime,
        targetStationId,
      });
    } else {
      createMutation.mutate({ startTime, endTime, targetStationId });
    }
  };

  const handleMoveUp = (entry: ScheduleEntry, allEntries: ScheduleEntry[]) => {
    const currentIndex = allEntries.findIndex((e) => e.id === entry.id);
    if (currentIndex === 0) return;

    const newOrder = [...allEntries];
    [newOrder[currentIndex - 1], newOrder[currentIndex]] = [
      newOrder[currentIndex],
      newOrder[currentIndex - 1],
    ];

    reorderMutation.mutate(newOrder.map((e) => e.id));
  };

  const handleMoveDown = (entry: ScheduleEntry, allEntries: ScheduleEntry[]) => {
    const currentIndex = allEntries.findIndex((e) => e.id === entry.id);
    if (currentIndex === allEntries.length - 1) return;

    const newOrder = [...allEntries];
    [newOrder[currentIndex], newOrder[currentIndex + 1]] = [
      newOrder[currentIndex + 1],
      newOrder[currentIndex],
    ];

    reorderMutation.mutate(newOrder.map((e) => e.id));
  };

  const handleDelete = (entryId: number) => {
    setDeletingId(entryId);
    deleteMutation.mutate(entryId);
  };

  if (!isOpen) return null;

  const isLoading = isLoadingSchedule || isLoadingStations;
  const sortedSchedule = schedule ? [...schedule].sort((a, b) => a.position - b.position) : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div className="relative max-w-3xl w-full mx-4 max-h-[90vh] bg-slate-950 border border-slate-800 rounded-xl shadow-2xl overflow-hidden">
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 rounded-full transition-colors"
          aria-label="Close modal"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Scrollable content */}
        <div className="overflow-y-auto max-h-[90vh] p-6">
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-slate-100 mb-2">Edit Schedule</h2>
            <p className="text-slate-400">{stationName}</p>
          </div>

          {isLoading ? (
            <div className="space-y-4">
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 animate-pulse">
                <div className="h-6 bg-slate-800 rounded w-48 mb-4"></div>
                <div className="h-10 bg-slate-800 rounded"></div>
              </div>
            </div>
          ) : stations ? (
            <>
              {/* Form */}
              <ScheduleEntryForm
                stations={stations}
                currentStationId={stationId}
                onSubmit={handleSubmit}
                isPending={createMutation.isPending || updateMutation.isPending}
                editingEntry={editingEntry}
                onCancelEdit={() => setEditingEntry(null)}
              />

              {/* Schedule entries list */}
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Current Schedule
                </h3>

                {sortedSchedule.length === 0 ? (
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center">
                    <p className="text-slate-400 mb-2">No schedule configured</p>
                    <p className="text-sm text-slate-500">Add time ranges to define when this station plays</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {sortedSchedule.map((entry, index) => (
                      <ScheduleEntryItem
                        key={entry.id}
                        entry={entry}
                        stations={stations}
                        onMoveUp={() => handleMoveUp(entry, sortedSchedule)}
                        onMoveDown={() => handleMoveDown(entry, sortedSchedule)}
                        onEdit={() => setEditingEntry(entry)}
                        onDelete={() => handleDelete(entry.id)}
                        isFirst={index === 0}
                        isLast={index === sortedSchedule.length - 1}
                        isDeleting={deletingId === entry.id}
                      />
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
