/**
 * State + handlers for the Home long-press action sheet.
 *
 * Only actions backed by an existing API: Play now (the screen's own play
 * handler) and Go to artist (GET /artists list → match by name → push
 * /artist/{id}). Play next / Add to queue have no backend endpoint yet.
 */
import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import { getArtists } from '@music-minion/shared';
import type { ArtistStats, Track } from '@music-minion/shared';
import { findArtistId } from '../features/home/trackRow';
import type { TrackActionKey } from '../features/home/trackRow';

interface Target {
  track: Track;
  index: number;
}

export interface TrackActionsState {
  sheetTrack: Track | null;
  busyKey: TrackActionKey | null;
  open: (track: Track, index: number) => void;
  close: () => void;
  select: (key: TrackActionKey) => void;
}

const ARTISTS_KEY = ['artists', 'list', 'all'] as const;

export function useTrackActions(onPlay: (track: Track, index: number) => void): TrackActionsState {
  const [target, setTarget] = useState<Target | null>(null);
  const close = useCallback((): void => setTarget(null), []);
  const { busy, goToArtist } = useGoToArtist(close);

  const select = useCallback(
    (key: TrackActionKey): void => {
      if (!target) return;
      if (key === 'artist') {
        void goToArtist(target.track.artist ?? '');
        return;
      }
      setTarget(null);
      onPlay(target.track, target.index);
    },
    [target, goToArtist, onPlay]
  );

  const open = useCallback((track: Track, index: number): void => setTarget({ track, index }), []);
  return { sheetTrack: target?.track ?? null, busyKey: busy ? 'artist' : null, open, close, select };
}

function useGoToArtist(onDone: () => void): { busy: boolean; goToArtist: (artist: string) => Promise<void> } {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const goToArtist = useCallback(
    async (artist: string): Promise<void> => {
      setBusy(true);
      try {
        const artists = await queryClient.fetchQuery({ queryKey: ARTISTS_KEY, queryFn: () => getArtists(), staleTime: 5 * 60_000 });
        openArtistPage(artists, artist);
      } catch (err) {
        Toast.show({ type: 'error', text1: "Couldn't load artists", text2: err instanceof Error ? err.message : 'Unknown error' });
      } finally {
        setBusy(false);
        onDone();
      }
    },
    [queryClient, onDone]
  );
  return { busy, goToArtist };
}

function openArtistPage(artists: ArtistStats[], artist: string): void {
  const id = findArtistId(artists, artist);
  if (id === null) {
    Toast.show({ type: 'info', text1: 'No artist page', text2: `${artist} isn't a SoundCloud artist you track` });
    return;
  }
  router.push(`/artist/${id}`);
}
