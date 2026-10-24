import { useEffect, useRef } from 'react';
import TrackPlayer, { PlayerCommand } from '@rntp/player';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { getDefaultApiClient } from '@music-minion/shared';
import { resolveStreamUrl } from '../services/e2eHooks';
import {
  registerForegroundPlaybackListeners,
  resetRetryTracking,
} from '../services/playbackEvents';

let isSetup = false;

/**
 * Backend artwork URL for a track. Mirrors getStreamUrl: baseUrl already
 * includes the `/api` prefix. Used for lockscreen art via setMediaItem.
 */
function getArtworkUrl(trackId: number): string {
  return `${getDefaultApiClient().getBaseUrl()}/tracks/${trackId}/artwork`;
}

function setupPlayer(): void {
  if (isSetup) return;
  try {
    TrackPlayer.setupPlayer({
      contentType: 'music',
    });
    TrackPlayer.setCommands({
      capabilities: [
        PlayerCommand.PlayPause,
        PlayerCommand.Next,
        PlayerCommand.Previous,
        PlayerCommand.Seek,
        PlayerCommand.Stop,
      ],
      handling: 'native',
    });
    isSetup = true;
  } catch {
    isSetup = true;
  }
}

/**
 * Drives RNTP from the player store: load, play/pause, volume, seeks and
 * scrobble timing. Mount it ONCE, via <PlaybackEngine /> (renders null).
 *
 * It subscribes to the whole store, so it must not live in a component that
 * renders UI: every store change would re-render that tree. It also holds no
 * position state. UI reads position through usePlaybackPosition in leaf
 * components only. (Before, this hook was usePlayer(): it polled RNTP at 4Hz
 * and was called by PlayerBar and NowPlaying, so both re-rendered their whole
 * trees 4x a second, paused or not. A second mount in NowPlaying also had its
 * own lastLoadedTrackIdRef and re-ran setMediaItem when the player opened.)
 */
export function usePlaybackEngine(): void {
  const store = usePlayerStore();
  const lastLoadedTrackIdRef = useRef<number | null>(null);
  const scrobbleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setupPlayer();
    // End/error handling lives in services/playbackEvents.ts (shared with the
    // background headless handler); registration is module-guarded.
    registerForegroundPlaybackListeners();
  }, []);

  // Load track into RNTP when currentTrack changes and this device is active
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack) return;
    if (!isSetup) return;
    if (lastLoadedTrackIdRef.current === store.currentTrack.id) return;

    const track = store.currentTrack;
    lastLoadedTrackIdRef.current = track.id;
    // New playthrough — this track gets one in-place retry before skip
    resetRetryTracking();

    const loadTrack = (): void => {
      try {
        TrackPlayer.setMediaItem({
          mediaId: track.id.toString(),
          url: resolveStreamUrl(track.id),
          title: track.title,
          artist: track.artist ?? 'Unknown Artist',
          duration: track.duration,
          artworkUrl: getArtworkUrl(track.id),
        });

        const pos = getCurrentPosition(store) / 1000;
        if (pos > 1) {
          TrackPlayer.seekTo(pos);
        }

        if (store.isPlaying) {
          TrackPlayer.play();
        }
      } catch (err) {
        store.setPlaybackError(
          err instanceof Error ? err.message : 'Failed to load track'
        );
      }
    };

    loadTrack();
  }, [store.currentTrack?.id, store.isThisDeviceActive]);

  // Play/pause sync
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack || !isSetup) return;

    if (store.isPlaying) {
      TrackPlayer.play();
    } else {
      TrackPlayer.pause();
    }
  }, [store.isPlaying, store.isThisDeviceActive]);

  // Pause when device becomes inactive
  useEffect(() => {
    if (!store.isThisDeviceActive && isSetup) {
      TrackPlayer.pause();
    }
  }, [store.isThisDeviceActive]);

  // Sync store volume/mute to RNTP (setVolume range is 0.0-1.0, same as store)
  useEffect(() => {
    if (!isSetup) return;
    TrackPlayer.setVolume(store.isMuted ? 0 : store.volume);
  }, [store.volume, store.isMuted]);

  // Apply seeks to RNTP. Single source of truth for both local seeks
  // (seek() sets lastSeekAt) and remote WS seeks (syncState sets lastSeekAt),
  // mirroring web's lastSeekAt guard. Avoids double-applying a local seek.
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack || !isSetup) return;
    if (store.lastSeekAt === 0) return;

    TrackPlayer.seekTo(getCurrentPosition(store) / 1000);
  }, [store.lastSeekAt, store.isThisDeviceActive]);

  // Scrobble tracking
  useEffect(() => {
    if (!store.isPlaying || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.scrobbledThisPlaythrough) return;

    const duration = (store.currentTrack.duration ?? 0) * 1000;
    const threshold = Math.min(duration * 0.5, 30000);
    const currentPos = getCurrentPosition(store);
    const remaining = threshold - currentPos;

    if (remaining <= 0) {
      store.onTrackPlayed(store.currentTrack.id, currentPos);
      return;
    }

    scrobbleTimerRef.current = setTimeout(() => {
      const pos = getCurrentPosition(usePlayerStore.getState());
      const trackId = usePlayerStore.getState().currentTrack?.id;
      if (trackId && !usePlayerStore.getState().scrobbledThisPlaythrough) {
        usePlayerStore.getState().onTrackPlayed(trackId, pos);
      }
    }, remaining);

    return () => {
      if (scrobbleTimerRef.current) clearTimeout(scrobbleTimerRef.current);
    };
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough]);
}
