import { useStoriesAutoplay, useStoriesListenReporter, useStoriesTrackEnd } from '../../hooks/useStoriesPlayback';

/**
 * Keeps a Stories session playing after the user leaves /stories: track-end
 * advance, autoplay of the next story and 5-second listen reports. Mounted
 * once in the root layout. Renders nothing, so listen-tally updates only
 * re-render this node. Inert until the Stories page starts a session.
 */
export function StoriesPlaybackBridge(): null {
  useStoriesAutoplay();
  useStoriesTrackEnd();
  useStoriesListenReporter();
  return null;
}
