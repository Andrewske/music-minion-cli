/**
 * Current track position in seconds, whichever device is playing.
 *
 * LEAF USE ONLY: this hook re-renders its caller once a second while a track
 * plays. Call it from the small components that draw position (the mini bar's
 * progress line, the full player's seek slider), never from a screen root.
 *
 * This device: polls RNTP at 1Hz (the time text only shows whole seconds).
 * State is a plain number, so a poll that reads the same value (paused)
 * doesn't re-render. Another device: RNTP is idle, so derive it from the
 * synced store clock on the same 1Hz tick. Both are clamped to the current
 * track's duration: the remote value is an extrapolation and runs on forever
 * if the playing device goes quiet.
 */
import { useEffect, useState } from 'react';
import TrackPlayer from '@rntp/player';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';
import { playbackPositionSec, readsStoreClock } from '../../features/player/progress';

const TICK_MS = 1000;

function readPositionSec(): number {
  const state = usePlayerStore.getState();
  const useStore = readsStoreClock(state.isThisDeviceActive, Date.now() - state.lastSeekAt);
  return playbackPositionSec({
    isThisDeviceActive: !useStore,
    localPositionSec: useStore ? 0 : TrackPlayer.getProgress().position,
    remotePositionMs: getCurrentPosition(state),
    durationSec: state.currentTrack?.duration,
  });
}

export function usePlaybackPosition(): number {
  const isThisDeviceActive = usePlayerStore((s) => s.isThisDeviceActive);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const trackId = usePlayerStore((s) => s.currentTrack?.id);
  const lastSeekAt = usePlayerStore((s) => s.lastSeekAt);
  const [position, setPosition] = useState(readPositionSec);

  useEffect(() => {
    // Re-read now on track change, seek, pause/resume or device switch,
    // then tick while playing. setState bails out when the value is equal.
    setPosition(readPositionSec());
    if (!isPlaying) return;
    const timer = setInterval(() => setPosition(readPositionSec()), TICK_MS);
    return () => clearInterval(timer);
  }, [isThisDeviceActive, isPlaying, trackId, lastSeekAt]);

  return position;
}
