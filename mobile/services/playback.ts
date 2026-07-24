/**
 * Background (headless) event handler — registered in index.js via
 * TrackPlayer.registerBackgroundEventHandler. On Android RNTP routes events
 * here ONLY while the app is backgrounded (foregrounded events go to the
 * NativeEventEmitter listeners instead), so this must stay registered for
 * lockscreen/background playback to keep advancing.
 *
 * All actual end/error logic lives in playbackEvents.ts (shared with the
 * foreground listeners) — see that module for the dedupe rationale.
 */
import type { BackgroundEvent } from '@rntp/player';
import { handlePlaybackEvent } from './playbackEvents';

module.exports = async function (event: BackgroundEvent): Promise<void> {
  handlePlaybackEvent(event);
};
