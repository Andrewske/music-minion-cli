import { useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { usePlayerStore } from '../stores/playerStore';
import { usePlaylistOrganizer } from '../hooks/usePlaylistOrganizer';
import { getPlaylistTracks } from '../api/playlists';
import { CurrentTrackBanner } from '../components/organizer/CurrentTrackBanner';
import { UnassignedTrackTable } from '../components/organizer/UnassignedTrackTable';
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
  } = usePlaylistOrganizer({ playlistId });

  // Load full track data for unassigned tracks
  const { data: allTracks } = useQuery({
    queryKey: ['playlist', playlistId, 'tracks'],
    queryFn: () => getPlaylistTracks(playlistId),
  });

  // Use Set for O(1) lookup
  const unassignedSet = new Set(unassignedTrackIds);
  const unassignedTracks = allTracks?.tracks.filter((t) => unassignedSet.has(t.id)) ?? [];

  // Handle assigning current track to a bucket
  const handleAssignCurrentTrack = useCallback(
    async (bucketId: string): Promise<void> => {
      if (!currentTrack) return;

      await assignTrack(bucketId, currentTrack.id);

      // Auto-advance to next unassigned track
      const remainingUnassigned = unassignedTrackIds.filter((id) => id !== currentTrack.id);
      const tracks = allTracks?.tracks;
      if (remainingUnassigned.length > 0 && tracks) {
        const nextTrack = tracks.find((t) => t.id === remainingUnassigned[0]);
        if (nextTrack) {
          // Convert PlaylistTrackEntry to Track format for player
          await play(
            {
              id: nextTrack.id,
              title: nextTrack.title,
              artist: nextTrack.artist,
            },
            { type: 'playlist', playlist_id: playlistId }
          );
        }
      }
    },
    [currentTrack, assignTrack, unassignedTrackIds, allTracks, play, playlistId]
  );

  // Keyboard handler for Shift+1-0
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (!e.shiftKey) return;
      if (!currentTrack) return;

      // Check if typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      const num = parseInt(e.key);
      if (isNaN(num)) return;

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

        {/* Buckets section placeholder - will be in next task */}
        <div className="mb-6">
          <h2 className="text-sm font-medium text-white/60 mb-2">Buckets</h2>
          <div className="bg-obsidian-surface border border-obsidian-border rounded-lg p-8 text-center">
            <div className="text-white/50 text-sm">
              {buckets.length === 0
                ? 'No buckets yet. Create buckets to organize tracks.'
                : `${buckets.length} bucket${buckets.length !== 1 ? 's' : ''} • Bucket list coming in next task`}
            </div>
          </div>
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
  );
}
