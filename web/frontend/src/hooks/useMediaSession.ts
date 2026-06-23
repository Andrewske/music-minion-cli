import { useEffect } from 'react';
import type { Track } from '@music-minion/shared';

const FALLBACK_ARTWORK = '/media-artwork-fallback.svg';

interface MediaSessionActions {
  play: () => void;
  pause: () => void;
  next: () => void;
  prev: () => void;
}

function buildMetadata(track: Track): MediaMetadata {
  return new MediaMetadata({
    title: track.title || 'Unknown Title',
    artist: track.artist || 'Unknown Artist',
    album: track.album || '',
    artwork: [
      { src: `/api/tracks/${track.id}/artwork`, sizes: '512x512', type: 'image/jpeg' },
      { src: FALLBACK_ARTWORK, sizes: '512x512', type: 'image/svg+xml' },
    ],
  });
}

/**
 * Bridges the active track + player controls to the browser Media Session API,
 * so Android Chrome (and other platforms) show track metadata and transport
 * controls in their media notification instead of "tab is playing".
 *
 * Effects no-op gracefully when the API is unavailable (older browsers, SSR).
 */
export function useMediaSession(
  currentTrack: Track | null,
  isPlaying: boolean,
  actions: MediaSessionActions,
): void {
  // Metadata: refresh on track change.
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    navigator.mediaSession.metadata = currentTrack ? buildMetadata(currentTrack) : null;
  }, [currentTrack]);

  // Playback state: keeps the notification play/pause icon in sync.
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    navigator.mediaSession.playbackState = currentTrack
      ? (isPlaying ? 'playing' : 'paused')
      : 'none';
  }, [currentTrack, isPlaying]);

  // Action handlers: wire notification controls to existing player actions.
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    const session = navigator.mediaSession;

    session.setActionHandler('play', () => actions.play());
    session.setActionHandler('pause', () => actions.pause());
    session.setActionHandler('previoustrack', () => actions.prev());
    session.setActionHandler('nexttrack', () => actions.next());

    return () => {
      session.setActionHandler('play', null);
      session.setActionHandler('pause', null);
      session.setActionHandler('previoustrack', null);
      session.setActionHandler('nexttrack', null);
    };
  }, [actions]);
}
