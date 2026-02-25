import { useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  DndContext,
  closestCenter,
  pointerWithin,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
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

      await assignTrack(bucketId, currentTrack.id);
      playNextUnassignedTrack(currentTrack.id);
    },
    [currentTrack, assignTrack, playNextUnassignedTrack]
  );

  // Handle drag end events
  const handleDragEnd = async (event: DragEndEvent): Promise<void> => {
    const { active, over } = event;

    if (!over) return;

    const dragType = active.data.current?.type;

    if (dragType === 'unassigned-track') {
      // Validate drop target is a bucket
      if (over.data.current?.type !== 'bucket') return;

      const trackId = active.id as number;
      const bucketId = over.id as string;

      try {
        await assignTrack(bucketId, trackId);
        playNextUnassignedTrack(trackId);
      } catch (error) {
        console.error('Failed to assign track:', error);
        toast.error('Failed to assign track to bucket');
      }
    }
    // bucket-track type is handled by SortableContext within buckets
  };

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
      onDragEnd={handleDragEnd}
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
    </DndContext>
  );
}
