/**
 * Renders nothing; hosts usePlaybackEngine so its whole-store subscription
 * re-renders only this null component, not the player UI around it.
 */
import { usePlaybackEngine } from '../../hooks/usePlaybackEngine';

export function PlaybackEngine(): null {
  usePlaybackEngine();
  return null;
}
