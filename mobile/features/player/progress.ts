/**
 * Playback position helpers shared by the mini bar progress line and the
 * full player's seek slider.
 */

export interface PositionInput {
  isThisDeviceActive: boolean;
  /** RNTP position in seconds (only meaningful when this device plays). */
  localPositionSec: number;
  /** Store-derived position in ms (getCurrentPosition), for remote playback. */
  remotePositionMs: number;
  /** Track duration in seconds; the position never runs past it. */
  durationSec: number | undefined;
}

/**
 * Seconds into the track, from RNTP here or the synced store elsewhere.
 * The remote value is extrapolated from the last broadcast (positionMs +
 * time since trackStartedAt), so it keeps growing if the playing device
 * stalls or never reports the track change. Clamp it to the duration.
 */
export function playbackPositionSec(input: PositionInput): number {
  const sec = input.isThisDeviceActive ? input.localPositionSec : input.remotePositionMs / 1000;
  return clampToDuration(Number.isFinite(sec) && sec > 0 ? sec : 0, input.durationSec);
}

/** Cap at the duration when it is known; unknown durations pass through. */
export function clampToDuration(positionSec: number, durationSec: number | undefined): number {
  if (!durationSec || durationSec <= 0 || !Number.isFinite(durationSec)) return positionSec;
  return Math.min(positionSec, durationSec);
}

/** 0..1 fraction of the track played. 0 when the duration is unknown. */
export function progressFraction(positionSec: number, durationSec: number | undefined): number {
  if (!durationSec || durationSec <= 0 || !Number.isFinite(positionSec)) return 0;
  return Math.min(1, Math.max(0, positionSec / durationSec));
}
