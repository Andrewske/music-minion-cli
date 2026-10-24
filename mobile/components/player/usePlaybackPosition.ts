/**
 * Current track position in seconds, whichever device is playing.
 *
 * This device: RNTP's polled position (passed in from usePlayer).
 * Another device: RNTP is idle, so derive it from the synced store clock and
 * tick once a second while playing so the progress line keeps moving.
 * Both are clamped to the current track's duration: the remote value is an
 * extrapolation and runs on forever if the playing device goes quiet.
 */
import { useEffect, useState } from 'react';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';
import { playbackPositionSec } from '../../features/player/progress';

const REMOTE_TICK_MS = 1000;

export function usePlaybackPosition(localPositionSec: number): number {
  const isThisDeviceActive = usePlayerStore((s) => s.isThisDeviceActive);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const durationSec = usePlayerStore((s) => s.currentTrack?.duration);
  const [, setTick] = useState(0);

  useEffect(() => {
    if (isThisDeviceActive || !isPlaying) return;
    const timer = setInterval(() => setTick((n) => n + 1), REMOTE_TICK_MS);
    return () => clearInterval(timer);
  }, [isThisDeviceActive, isPlaying]);

  return playbackPositionSec({
    isThisDeviceActive,
    localPositionSec,
    remotePositionMs: getCurrentPosition(usePlayerStore.getState()),
    durationSec,
  });
}
