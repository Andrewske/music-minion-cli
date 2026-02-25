import { useEffect, useCallback, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { toast } from 'react-toastify';
import { usePlayerStore } from '../stores/playerStore';
import { usePlaylistOrganizer } from '../hooks/usePlaylistOrganizer';
import { getPlaylistTracks } from '../api/playlists';
import { CurrentTrackBanner } from '../components/organizer/CurrentTrackBanner';
import { UnassignedTrackTable } from '../components/organizer/UnassignedTrackTable';
import { BucketList } from '../components/organizer/BucketList';
import { Button } from '../components/ui/button';
import type { PlaylistOrganizerProps } from './PlaylistOrganizer.types';

export function PlaylistOrganizer({
  playlistId,
  playlistName,
  playlistType,
}: PlaylistOrganizerProps): JSX.Element {
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const play = usePlayerStore((s) => s.play);

  const {
    session,
    isLoading,
    buckets,
    unassignedTrackIds,
    assignTrack,
    unassignTrack,
    applyOrder,
    getBucketByIndex,
    isAssigning,
    isApplying,
    createBucket,
    updateBucket,
    deleteBucket,
    moveBucket,
    shuffleBucket,
    reorderTracks,
  } = usePlaylistOrganizer({ playlistId });

  // Load full track data for unassigned tracks
  const { data: allTracks } = useQuery({
    queryKey: ['playlist', playlistId, 'tracks'],
    queryFn: () => getPlaylistTracks(playlistId),
  });

  // Use Set for O(1) lookup
  const unassignedSet = new Set(unassignedTrackIds);
  const unassignedTracks = allTracks?.tracks.filter((t) => unassignedSet.has(t.id)) ?? [];

  // Configure drag-and-drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 }, // Prevents accidental drags
    }),
    useSensor(KeyboardSensor)
  );

  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDragType, setActiveDragType] = useState<'unassigned-track' | 'bucket-track' | null>(null);

  // Auto-advance helper function (used by both keyboard shortcuts and drag-and-drop)
  const playNextUnassignedTrack = useCallback(
    (excludeTrackId: number): void => {
      const remainingUnassigned = unassignedTrackIds.filter((id) => id !== excludeTrackId);
      if (remainingUnassigned.length > 0 && allTracks?.tracks) {
        const nextTrack = allTracks.tracks.find((t) => t.id === remainingUnassigned[0]);
        if (nextTrack) {
          play(
            { id: nextTrack.id, title: nextTrack.title, artist: nextTrack.artist },
            { type: 'playlist', playlist_id: playlistId }
          );
        }
      }
    },
    [unassignedTrackIds, allTracks, playlistId, play]
  );

  // Handle assigning current track to a bucket
  const handleAssignCurrentTrack = useCallback(
    async (bucketId: string): Promise<void> => {
      if (!currentTrack) return;

      // Find which bucket (if any) currently contains this track
      const currentBucket = buckets.find((b) => b.track_ids.includes(currentTrack.id));

      // If already in target bucket, no-op
      if (currentBucket?.id === bucketId) return;

      await assignTrack(bucketId, currentTrack.id);

      // Only auto-advance if moving from unassigned
      if (!currentBucket) {
        playNextUnassignedTrack(currentTrack.id);
      }
    },
    [currentTrack, assignTrack, playNextUnassignedTrack]
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const { active } = event;
    setActiveId(active.id as number);
    setActiveDragType(active.data.current?.type as 'unassigned-track' | 'bucket-track');
  }, []);

  const handleDragCancel = useCallback(() => {
    setActiveId(null);
    setActiveDragType(null);
  }, []);

  // Memoize track display to avoid O(n*m) lookup on every render
  const activeTrackDisplay = useMemo(() => {
    if (!activeId || !activeDragType || !allTracks?.tracks) return null;

    if (activeDragType === 'unassigned-track') {
      const track = unassignedTracks.find(t => t.id === activeId);
      return track ? track.title : 'Unknown Track';
    }

    // Bucket track - find which bucket contains this track ID, then look up track details
    for (const bucket of buckets) {
      if (bucket.track_ids.includes(activeId)) {
        const track = allTracks.tracks.find(t => t.id === activeId);
        if (track) return `${bucket.emoji_id || '📦'} ${track.title}`;
      }
    }
    return 'Unknown Track';
  }, [activeId, activeDragType, unassignedTracks, buckets, allTracks]);

  // Handle drag end events
  const handleDragEnd = useCallback(
    async (event: DragEndEvent): Promise<void> => {
      try {
        const { active, over } = event;
        if (!over) return;

        const dragType = active.data.current?.type;

        // Case 1: Unassigned track → bucket (existing functionality)
        if (dragType === 'unassigned-track') {
          if (over.data.current?.type !== 'bucket') return;

          const trackId = active.id as number;
          const bucketId = over.id as string;

          // Type guard for development
          if (typeof trackId !== 'number' || typeof bucketId !== 'string') {
            console.error('Invalid drag data types:', { trackId, bucketId });
            return;
          }

          try {
            await assignTrack(bucketId, trackId);
            playNextUnassignedTrack(trackId);
          } catch (error) {
            console.error('Failed to assign track:', error);
            const message = error instanceof Error ? error.message : String(error);
            toast.error(`Failed to assign track ${trackId} to bucket ${bucketId}: ${message}`);
          }
          return;
        }

        // Case 2: Bucket track → different bucket OR unassigned (NEW)
        if (dragType === 'bucket-track') {
          const trackId = active.id as number;
          const sourceBucketId = active.data.current?.bucketId as string | undefined;

          // Type guards for development
          if (typeof trackId !== 'number') {
            console.error('Invalid track ID type:', trackId);
            return;
          }

          if (!sourceBucketId || typeof sourceBucketId !== 'string') {
            console.error('Missing or invalid source bucket ID in drag data:', sourceBucketId);
            return;
          }

          const overType = over.data.current?.type;

          // Case 2a: Bucket track → different bucket
          if (overType === 'bucket') {
            const targetBucketId = over.id as string;

            if (typeof targetBucketId !== 'string') {
              console.error('Invalid target bucket ID type:', targetBucketId);
              return;
            }

            // No-op if dropping on same bucket
            if (targetBucketId === sourceBucketId) return;

            try {
              await assignTrack(targetBucketId, trackId);
            } catch (error) {
              console.error('Failed to move track between buckets:', error);
              const message = error instanceof Error ? error.message : String(error);
              toast.error(`Failed to move track ${trackId} from bucket ${sourceBucketId} to ${targetBucketId}: ${message}`);
            }
            return;
          }

          // Case 2b: Bucket track → unassigned area
          if (overType === 'unassigned-area') {
            try {
              await unassignTrack(sourceBucketId, trackId);
            } catch (error) {
              console.error('Failed to unassign track:', error);
              const message = error instanceof Error ? error.message : String(error);
              toast.error(`Failed to unassign track ${trackId} from bucket ${sourceBucketId}: ${message}`);
            }
            return;
          }

          // Case 2c: Bucket track → track in different bucket (NEW)
          if (overType === 'bucket-track') {
            const targetBucketId = over.data.current?.bucketId as string | undefined;

            if (!targetBucketId || typeof targetBucketId !== 'string') {
              console.error('Missing or invalid target bucket ID in drag data:', targetBucketId);
              return;
            }

            // No-op if dropping in same bucket (within-bucket reordering handled by child)
            if (targetBucketId === sourceBucketId) return;

            try {
              await assignTrack(targetBucketId, trackId);
            } catch (error) {
              console.error('Failed to move track between buckets:', error);
              const message = error instanceof Error ? error.message : String(error);
              toast.error(`Failed to move track ${trackId} from bucket ${sourceBucketId} to ${targetBucketId}: ${message}`);
            }
            return;
          }
        }
      } finally {
        // Always clear state, even if early return or error
        setActiveId(null);
        setActiveDragType(null);
      }
    },
    [assignTrack, unassignTrack, playNextUnassignedTrack]
  );

  // Keyboard handler for Shift+1-0
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (!e.shiftKey) return;
      if (!currentTrack) return;

      // Check if typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      const digitMatch = e.code.match(/^(?:Digit|Numpad)(\d)$/);
      if (!digitMatch) return;
      const num = parseInt(digitMatch[1]);

      e.preventDefault();

      // Shift+1 = bucket index 0, Shift+0 = bucket index 9
      const bucketIndex = num === 0 ? 9 : num - 1;
      const bucket = getBucketByIndex(bucketIndex);

      if (bucket) {
        handleAssignCurrentTrack(bucket.id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentTrack, getBucketByIndex, handleAssignCurrentTrack]);

  // Handle playing a track from the table
  const handlePlayTrack = useCallback(
    (trackId: number): void => {
      const tracks = allTracks?.tracks;
      const track = tracks?.find((t) => t.id === trackId);
      if (track) {
        play(
          {
            id: track.id,
            title: track.title,
            artist: track.artist,
          },
          { type: 'playlist', playlist_id: playlistId }
        );
      }
    },
    [allTracks, play, playlistId]
  );

  // Handle applying the order
  const handleApplyOrder = useCallback(async (): Promise<void> => {
    await applyOrder();
  }, [applyOrder]);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter p-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-white/50 text-sm">Loading organizer...</div>
        </div>
      </div>
    );
  }

  // No session state
  if (!session) {
    return (
      <div className="min-h-screen bg-black font-inter p-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-white/50 text-sm">Failed to load organizer session.</div>
        </div>
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="min-h-screen bg-black font-inter p-6">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-lg font-medium text-white/90">{playlistName}</h1>
              <div className="text-xs text-white/40 mt-1">
                {playlistType === 'manual' ? 'Manual Playlist' : 'Smart Playlist'} •{' '}
                {unassignedTrackIds.length} unassigned
              </div>
            </div>

            <Button
              onClick={handleApplyOrder}
              disabled={isApplying || unassignedTrackIds.length > 0}
              className="bg-obsidian-accent hover:bg-obsidian-accent/80"
            >
              {isApplying ? 'Applying...' : 'Apply Order'}
            </Button>
          </div>

          {/* Current track banner */}
          <CurrentTrackBanner buckets={buckets} />

          {/* Unassigned tracks table */}
          <div className="mb-6">
            <h2 className="text-sm font-medium text-white/60 mb-2">Unassigned Tracks</h2>
            <UnassignedTrackTable
              tracks={unassignedTracks}
              currentTrackId={currentTrack?.id ?? null}
              onTrackClick={handlePlayTrack}
            />
          </div>

          {/* Buckets section */}
          <div className="mb-6">
            <h2 className="text-sm font-medium text-white/60 mb-2">Buckets</h2>
            <BucketList
              buckets={buckets}
              allTracks={allTracks?.tracks ?? []}
              onCreateBucket={createBucket}
              onMoveBucket={moveBucket}
              onShuffleBucket={shuffleBucket}
              onDeleteBucket={deleteBucket}
              onUpdateBucket={updateBucket}
              onReorderTracks={reorderTracks}
            />
          </div>

          {/* Status bar */}
          <div className="fixed bottom-16 left-0 right-0 bg-obsidian-surface border-t border-obsidian-border px-4 py-2 text-xs text-white/40">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div>
                {isAssigning ? 'Assigning track...' : 'Ready'}
              </div>
              <div>
                {buckets.length > 0 && (
                  <span>
                    Shift+1-{Math.min(buckets.length, 9)} to assign current track
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <DragOverlay>
        {activeTrackDisplay ? (
          <div className="bg-obsidian-surface border border-obsidian-accent rounded px-3 py-2 shadow-xl opacity-90 cursor-grabbing">
            <div className="text-sm text-white/90 truncate max-w-md">
              {activeTrackDisplay}
            </div>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
