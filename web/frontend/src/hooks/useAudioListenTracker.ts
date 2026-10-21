import { useEffect } from 'react';
import type { ListenEvent, ListenEventKind } from '../lib/feedListen';
import { SEEK_REQUEST_EVENT } from '../lib/audioSource';
import { useListenStore } from '../stores/listenStore';
import { getCurrentPosition, usePlayerStore, type PlayerStore } from '../stores/playerStore';

export type ListenMedia = Pick<
  HTMLMediaElement,
  'currentTime' | 'duration' | 'addEventListener' | 'removeEventListener'
> & {
  dataset: DOMStringMap;
};

type RecordFn = (event: ListenEvent) => void;

const EVENT_KINDS: ReadonlyArray<[string, ListenEventKind]> = [
  ['timeupdate', 'progress'],
  ['seeking', 'seek'],
  ['seeked', 'seek'],
  [SEEK_REQUEST_EVENT, 'seek'],
  // Re-caps a seek target recorded before the media knew its length.
  ['durationchange', 'duration'],
];

/** A seek request carries its target; every other event reads the element's position. */
function eventPositionMs(el: ListenMedia, event: Event): number {
  if (event instanceof CustomEvent && typeof event.detail === 'number') return event.detail;
  return el.currentTime * 1000;
}

/** Wires one audio element's real playback events into `record`; returns a detach function. */
export function attachListenTracker(el: ListenMedia, source: string, record: RecordFn): () => void {
  const handlers = EVENT_KINDS.map(([type, kind]) => {
    const handler = (event: Event): void => {
      // dataset.trackId is set by usePlayer whenever a track is bound.
      const trackId = Number(el.dataset.trackId);
      if (!el.dataset.trackId || !Number.isFinite(trackId)) return;
      const positionMs = eventPositionMs(el, event);
      record({ kind, source, trackId, positionMs, mediaDurationMs: el.duration * 1000 });
    };
    el.addEventListener(type, handler);
    return [type, handler] as const;
  });
  return () => handlers.forEach(([type, handler]) => el.removeEventListener(type, handler));
}

/**
 * Records every store seek target as it is requested. React batches renders,
 * so two seeks in one tick reach the audio element as a single seek.
 * lastSeekAt is a strictly increasing token (nextSeekStamp), so seeks in the
 * same millisecond still each show up here.
 */
export function attachStoreSeekTracker(record: RecordFn): () => void {
  return usePlayerStore.subscribe((state: PlayerStore, prev: PlayerStore) => {
    const track = state.currentTrack;
    if (state.lastSeekAt === prev.lastSeekAt || !track || !state.isAudioLeader) return;
    record({
      kind: 'seek',
      source: 'store',
      trackId: track.id,
      positionMs: getCurrentPosition(state),
      trackDurationMs: (track.duration ?? 0) * 1000,
    });
  });
}

/** Listen accounting on the player's own audio elements. Mount once, next to usePlayer. */
export function useAudioListenTracker(audioA: ListenMedia | null, audioB: ListenMedia | null): void {
  useEffect(() => {
    if (!audioA || !audioB) return;
    const record = useListenStore.getState().record;
    const detachers = [
      attachListenTracker(audioA, 'A', record),
      attachListenTracker(audioB, 'B', record),
      attachStoreSeekTracker(record),
    ];
    return () => detachers.forEach((detach) => detach());
  }, [audioA, audioB]);
}
