import { Event, PlaybackState, type BackgroundEvent } from '@rntp/player';
import { usePlayerStore } from '../stores/playerStore';

module.exports = async function (event: BackgroundEvent): Promise<void> {
  switch (event.type) {
    case Event.PlaybackStateChanged: {
      const { state } = event;
      if (state === PlaybackState.Ended) {
        const store = usePlayerStore.getState();
        if (store.currentContext?.type !== 'comparison') {
          store.next();
        }
      }
      break;
    }
    case Event.PlaybackError: {
      const trackTitle = usePlayerStore.getState().currentTrack?.title ?? 'Unknown';
      usePlayerStore.getState().setPlaybackError(`Failed to load: ${trackTitle}`);
      setTimeout(() => usePlayerStore.getState().next(), 2000);
      break;
    }
  }
};
