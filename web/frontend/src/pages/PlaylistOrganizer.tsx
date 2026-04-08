import { useEffect, useCallback, useState, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
import { arrayMove } from '@dnd-kit/sortable';
import { toast } from 'react-toastify';
import { GripVertical, ChevronDown, ChevronRight, RotateCcw, Radar, Loader2 } from 'lucide-react';
import { triggerDiscoverySync, getDiscoverySyncStatus } from '../api/discovery';
import type { DiscoverySyncStatus } from '../api/discovery';
import { usePlayerStore } from '../stores/playerStore';
import { usePlaylistOrganizer } from '../hooks/usePlaylistOrganizer';
import { getPlaylistTracks } from '../api/playlists';
import { CurrentTrackBanner } from '../components/organizer/CurrentTrackBanner';
import { UnassignedTrackTable } from '../components/organizer/UnassignedTrackTable';
import { BucketList } from '../components/organizer/BucketList';
import { Button } from '../components/ui/button';
import type { PlaylistOrganizerProps } from './PlaylistOrganizer.types';
import type { PlaylistTrackEntry } from '../types';

function DragPreviewRow({ track }: { track: PlaylistTrackEntry }): JSX.Element {
  return (
    <div className="bg-obsidian-surface border-2 border-obsidian-accent rounded shadow-2xl cursor-grabbing transform scale-105 opacity-95">
      <div className="flex items-center w-full px-3 py-2 text-sm">
        {/* Drag handle icon */}
        <div className="flex-none w-10 text-white/30">
          <GripVertical className="w-4 h-4" />
        </div>

        {/* Title - flex 3 */}
        <div className="flex-[3] min-w-0 px-2 text-white/90 truncate">
          {track.title}
        </div>

        {/* Artist - flex 2 */}
        <div className="flex-[2] min-w-0 px-2 text-white/70 truncate">
          {track.artist ?? '-'}
        </div>

        {/* BPM - fixed 50px */}
        <div className="flex-none w-[50px] px-2 text-white/60 text-center">
          {track.bpm ? Math.round(track.bpm) : '-'}
        </div>

        {/* Key - fixed 60px */}
        <div className="flex-none w-[60px] px-2 text-white/60 text-center">
          {track.key_signature ?? '-'}
        </div>

        {/* Rating - fixed 70px */}
        <div className="flex-none w-[70px] px-2 text-white/60 text-center">
          {track.rating ? Math.round(track.rating) : '-'}
        </div>
      </div>
    </div>
  );
}

export function PlaylistOrganizer({
  playlistId,
  playlistName,
  playlistType,
  playlistLibrary,
  discoverySource,
}: PlaylistOrganizerProps): JSX.Element {
  const queryClient = useQueryClient();
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const play = usePlayerStore((s) => s.play);
  const shuffleEnabled = usePlayerStore((state) => state.shuffleEnabled);

  const {
    session,
    isLoading,
    buckets,
    unassignedTrackIds,
    assignTrack,
    unassignTrack,
    applyOrder,
    finalizeSession,
    getBucketByIndex,
    isApplying,
    isFinalizing,
    createBucket,
    updateBucket,
    deleteBucket,
    moveBucket,
    shuffleBucket,
    reorderTracks,
    linkBucket,
    syncBucketSoundCloud,
    syncingBucketId,
  } = usePlaylistOrganizer({ playlistId });

  // Load full track data for all tracks in playlist (high limit for organizer)
  const { data: allTracks } = useQuery({
    queryKey: ['playlist', playlistId, 'tracks', 'all'],
    queryFn: () => getPlaylistTracks(playlistId, { limit: 10000 }),
  });

  // Use Set for O(1) lookup
  const unassignedSet = new Set(unassignedTrackIds);
  const unassignedTracks = allTracks?.tracks.filter((t) => unassignedSet.has(t.id)) ?? [];

  // Compute date range from all tracks
  const dateRange = useMemo(() => {
    const tracks = allTracks?.tracks ?? [];
    const dates = tracks
      .map((t) => t.added_at)
      .filter((d): d is string => Boolean(d))
      .map((d) => {
        const normalized = d.replace(/\//g, '-').replace(' +0000', 'Z').replace(' ', 'T');
        return new Date(normalized);
      })
      .filter((d) => !isNaN(d.getTime()));
    if (dates.length === 0) return null;
    const oldest = new Date(Math.min(...dates.map((d) => d.getTime())));
    const newest = new Date(Math.max(...dates.map((d) => d.getTime())));
    const fmt = (d: Date): string => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `${fmt(oldest)} – ${fmt(newest)}`;
  }, [allTracks]);

  // Build reverse lookup map for O(1) performance (supports multi-bucket)
  const trackToBucketsMap = useMemo(() => {
    const map = new Map<number, Set<string>>();
    buckets.forEach((bucket) => {
      bucket.track_ids.forEach((trackId) => {
        if (!map.has(trackId)) {
          map.set(trackId, new Set());
        }
        map.get(trackId)!.add(bucket.id);
      });
    });
    return map;
  }, [buckets]);

  // Detect which buckets contain the current track
  const activeBucketIds = currentTrack
    ? trackToBucketsMap.get(currentTrack.id) ?? new Set<string>()
    : new Set<string>();

  // Configure drag-and-drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 }, // Prevents accidental drags
    }),
    useSensor(KeyboardSensor)
  );

  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDragType, setActiveDragType] = useState<'unassigned-track' | 'bucket-track' | null>(null);
  const [isUnassignedExpanded, setIsUnassignedExpanded] = useState(true);
  const isDragOperationInProgress = useRef(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);


  // Assign/unassign current track to a bucket with toggle behavior (used by keyboard shortcuts and header clicks)
  const assignCurrentTrackToBucket = useCallback(
    async (bucketId: string): Promise<void> => {
      if (!currentTrack) return;

      // Check if track is already in this bucket
      const bucket = buckets.find(b => b.id === bucketId);
      const isInBucket = bucket?.track_ids.includes(currentTrack.id) ?? false;

      try {
        if (isInBucket) {
          // Toggle OFF: Unassign track from bucket
          await unassignTrack(bucketId, currentTrack.id);
        } else {
          // Toggle ON: Assign track to bucket
          await assignTrack(bucketId, currentTrack.id);
        }
      } catch (error) {
        console.error('Failed to toggle track assignment:', error);
        const message = error instanceof Error ? error.message : String(error);
        toast.error(`Failed to update track: ${message}`);
      }
    },
    [currentTrack, buckets, assignTrack, unassignTrack]
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const { active } = event;
    setActiveId(active.id as number);
    setActiveDragType(active.data.current?.type as 'unassigned-track' | 'bucket-track');

    // Global cursor override for consistent drag UX
    document.body.style.cursor = 'grabbing';
  }, []);

  const handleDragCancel = useCallback(() => {
    // Reset cursor immediately
    document.body.style.cursor = '';

    setActiveId(null);
    setActiveDragType(null);
  }, []);

  // Pre-compute Map for O(1) lookup of track details during drag operations
  const trackIdToTrackMap = useMemo(() => {
    const map = new Map<number, PlaylistTrackEntry>();
    if (allTracks?.tracks) {
      for (const track of allTracks.tracks) {
        map.set(track.id, track); // Store full track object
      }
    }
    return map;
  }, [allTracks]);

  // Get full track object for drag preview
  const activeTrack = useMemo(() => {
    if (!activeId) return null;
    return trackIdToTrackMap.get(activeId) ?? null;
  }, [activeId, trackIdToTrackMap]);

  // Handle drag end events
  const handleDragEnd = useCallback(
    async (event: DragEndEvent): Promise<void> => {
      // Reset cursor immediately
      document.body.style.cursor = '';

      // Prevent concurrent drag operations
      if (isDragOperationInProgress.current) {
        console.warn('Drag operation already in progress, ignoring');
        return;
      }

      try {
        isDragOperationInProgress.current = true;

        const { active, over } = event;

        // Clear drag state immediately to prevent loops
        setActiveId(null);
        setActiveDragType(null);

        const dragType = active.data.current?.type;

        // Special case: Bucket track dropped outside any drop zone = unassign
        if (!over && dragType === 'bucket-track') {
          const trackId = active.id as number;
          const sourceBucketId = active.data.current?.bucketId as string | undefined;

          if (typeof trackId !== 'number' || !sourceBucketId) {
            console.error('Invalid drag data for unassign:', { trackId, sourceBucketId });
            return;
          }

          try {
            await unassignTrack(sourceBucketId, trackId);
          } catch (error) {
            console.error('Failed to unassign track:', error);
            const message = error instanceof Error ? error.message : String(error);
            toast.error(`Failed to unassign track ${trackId}: ${message}`);
          }
          return;
        }

        if (!over) return;

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

          // Case 2b: Bucket track → track in different bucket (cross-bucket move)
          if (overType === 'bucket-track') {
            const targetBucketId = over.data.current?.bucketId as string | undefined;

            if (!targetBucketId || typeof targetBucketId !== 'string') {
              console.error('Missing or invalid target bucket ID in drag data:', targetBucketId);
              return;
            }

            // Case 2b-i: Within-bucket reordering (same bucket)
            if (targetBucketId === sourceBucketId) {
              const bucket = buckets.find((b) => b.id === sourceBucketId);
              if (!bucket) {
                console.error('Source bucket not found:', sourceBucketId);
                return;
              }

              const oldIndex = bucket.track_ids.indexOf(trackId);
              const newIndex = bucket.track_ids.indexOf(over.id as number);

              if (oldIndex === -1 || newIndex === -1) {
                console.error('Track not found in bucket for reordering:', { trackId, overId: over.id, trackIds: bucket.track_ids });
                return;
              }

              // Skip if no actual movement
              if (oldIndex === newIndex) return;

              const newOrder = arrayMove(bucket.track_ids, oldIndex, newIndex);

              try {
                await reorderTracks(sourceBucketId, newOrder);
              } catch (error) {
                console.error('Failed to reorder tracks within bucket:', error);
                const message = error instanceof Error ? error.message : String(error);
                toast.error(`Failed to reorder tracks in bucket ${sourceBucketId}: ${message}`);
              }
              return;
            }

            // Case 2b-ii: Cross-bucket move (different bucket)
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
      } catch (outerError) {
        console.error('Unexpected error in handleDragEnd:', outerError);
      } finally {
        // Always release the drag operation lock
        isDragOperationInProgress.current = false;
      }
    },
    [buckets, assignTrack, unassignTrack, reorderTracks]
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
        assignCurrentTrackToBucket(bucket.id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentTrack, getBucketByIndex, assignCurrentTrackToBucket]);

  // Save session ID when created/resumed
  useEffect(() => {
    if (session && playlistId) {
      localStorage.setItem(`organizer-session-${playlistId}`, session.id);
    }
  }, [session, playlistId]);

  // Handle playing a track from the table
  const handlePlayTrack = useCallback(
    (trackId: number): void => {
      const tracks = allTracks?.tracks;
      const track = tracks?.find((t) => t.id === trackId);
      const bucketIds = trackToBucketsMap.get(trackId);
      const bucketId = bucketIds && bucketIds.size > 0 ? Array.from(bucketIds)[0] : undefined;  // undefined for unassigned, pick first bucket if multi-bucket
      if (track && session) {
        play(
          {
            id: track.id,
            title: track.title,
            artist: track.artist,
          },
          {
            type: 'organizer',
            playlist_id: playlistId,
            session_id: session.id,
            bucket_id: bucketId,
            shuffle: shuffleEnabled
          }
        );
      }
    },
    [allTracks, play, playlistId, session, shuffleEnabled, trackToBucketsMap]
  );

  // Handle SoundCloud sync for a bucket
  const handleSyncSoundCloud = useCallback(async (bucketId: string): Promise<void> => {
    try {
      const result = await syncBucketSoundCloud(bucketId);
      toast.success(`SC sync: ${result.pulled} pulled, ${result.pushed_adds} added, ${result.pushed_removals} removed`);
    } catch (error) {
      toast.error(`SoundCloud sync failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [syncBucketSoundCloud]);

  // Clean up poll interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const handleSyncDiscovery = useCallback(async (dryRun: boolean = false): Promise<void> => {
    setIsSyncing(true);
    try {
      const { job_id } = await triggerDiscoverySync(dryRun);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const status: DiscoverySyncStatus = await getDiscoverySyncStatus(job_id);

          if (status.status === 'completed') {
            clearInterval(pollIntervalRef.current!);
            pollIntervalRef.current = null;
            setIsSyncing(false);
            const r = status.result!;
            toast.success(
              `Discovery sync: ${r.tracks_added_to_playlist} tracks added` +
              (r.mixes_added > 0 ? `, ${r.mixes_added} mixes` : '') +
              (r.dry_run ? ' (dry run)' : '')
            );
            queryClient.invalidateQueries({ queryKey: ['bucket-session'] });
            queryClient.invalidateQueries({ queryKey: ['playlists'] });
          } else if (status.status === 'failed') {
            clearInterval(pollIntervalRef.current!);
            pollIntervalRef.current = null;
            setIsSyncing(false);
            toast.error(`Sync failed: ${status.error}`);
          }
        } catch {
          // Polling error — continue trying
        }
      }, 1000);
    } catch (error) {
      setIsSyncing(false);
      toast.error(`Failed to start sync: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [queryClient]);

  // Handle applying the order (keeps session active)
  const handleApplyOrder = useCallback(async (): Promise<void> => {
    await applyOrder();
    toast.success('Playlist order applied');
  }, [applyOrder]);

  // Handle finalizing the session (closes organizing mode)
  const handleFinalize = useCallback(async (): Promise<void> => {
    await finalizeSession();
    localStorage.removeItem(`organizer-session-${playlistId}`);
    toast.success('Organizing session finalized');
  }, [finalizeSession, playlistId]);

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
                {dateRange && <> • {dateRange}</>}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {discoverySource && (
                <button
                  type="button"
                  onClick={() => handleSyncDiscovery(false)}
                  disabled={isSyncing}
                  className="p-1.5 text-white/40 hover:text-purple-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Sync Discovery"
                >
                  {isSyncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radar className="w-4 h-4" />}
                </button>
              )}
              <Button
                onClick={handleApplyOrder}
                disabled={isApplying || unassignedTrackIds.length > 0}
                className="bg-obsidian-accent hover:bg-obsidian-accent/80"
              >
                {isApplying ? 'Applying...' : 'Apply Order'}
              </Button>
              <Button
                onClick={handleFinalize}
                disabled={isFinalizing}
                variant="outline"
                size="icon"
                title="Reset session (close organizing mode)"
              >
                <RotateCcw className={`w-4 h-4 ${isFinalizing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {/* Current track banner */}
          <CurrentTrackBanner buckets={buckets} />

          {/* Unassigned tracks table */}
          <div className="mb-6">
            <div className="bg-obsidian-surface border border-obsidian-border rounded-lg overflow-hidden">
              {/* Header - clickable to expand/collapse */}
              <button
                type="button"
                onClick={() => setIsUnassignedExpanded(!isUnassignedExpanded)}
                className="flex items-center gap-2 px-3 py-2 w-full hover:bg-white/5 transition-colors cursor-pointer"
              >
                <span className="text-white/50">
                  {isUnassignedExpanded ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </span>

                <span className="text-sm font-medium text-white/90">
                  Unassigned Tracks
                </span>
                <span className="text-xs text-white/40">
                  ({unassignedTrackIds.length})
                </span>
              </button>

              {/* Expanded track table */}
              {isUnassignedExpanded && (
                <div className="border-t border-obsidian-border">
                  <UnassignedTrackTable
                    tracks={unassignedTracks}
                    currentTrackId={currentTrack?.id ?? null}
                    onTrackClick={handlePlayTrack}
                    isDragging={activeId !== null && activeDragType === 'unassigned-track'}
                    noBorder={true}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Buckets section - sticky container */}
          <div className="sticky top-0 z-10 bg-black pb-4">
            <h2 className="text-sm font-medium text-white/60 mb-2">Buckets</h2>
            <BucketList
              buckets={buckets}
              allTracks={allTracks?.tracks ?? []}
              activeBucketIds={activeBucketIds}
              onCreateBucket={createBucket}
              onMoveBucket={moveBucket}
              onShuffleBucket={shuffleBucket}
              onDeleteBucket={deleteBucket}
              onUpdateBucket={updateBucket}
              onTrackClick={handlePlayTrack}
              onBucketHeaderClick={assignCurrentTrackToBucket}
              currentTrack={currentTrack}
              parentPlaylistId={playlistId}
              parentLibrary={playlistLibrary}
              onLinkBucket={linkBucket}
              onSyncSoundCloud={handleSyncSoundCloud}
              syncingBucketId={syncingBucketId}
            />
          </div>
        </div>
      </div>

      <DragOverlay>
        {activeId && activeTrack ? (
          <DragPreviewRow track={activeTrack} />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
