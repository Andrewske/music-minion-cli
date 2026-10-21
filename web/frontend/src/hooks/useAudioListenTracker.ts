import { useEffect } from 'react';
import type { ListenEvent, ListenEventKind } from '../lib/feedListen';
import { useListenStore } from '../stores/listenStore';

export type ListenMedia = Pick<HTMLMediaElement, 'currentTime' | 'addEventListener' | 'removeEventListener'> & {
  dataset: DOMStringMap;
};

const EVENT_KINDS: ReadonlyArray<[string, ListenEventKind]> = [
  ['timeupdate', 'progress'],
  ['seeking', 'seek'],
  ['seeked', 'seek'],
];

/** Wires one audio element's real playback events into `record`; returns a detach function. */
export function attachListenTracker(
  el: ListenMedia,
  source: string,
  record: (event: ListenEvent) => void,
): () => void {
  const handlers = EVENT_KINDS.map(([type, kind]) => {
    const handler = (): void => {
      // dataset.trackId is set by usePlayer whenever a track is bound.
      const trackId = Number(el.dataset.trackId);
      if (!el.dataset.trackId || !Number.isFinite(trackId)) return;
      record({ kind, source, trackId, positionMs: el.currentTime * 1000 });
    };
    el.addEventListener(type, handler);
    return [type, handler] as const;
  });
  return () => handlers.forEach(([type, handler]) => el.removeEventListener(type, handler));
}

/** Listen accounting on the player's own audio elements. Mount once, next to usePlayer. */
export function useAudioListenTracker(audioA: ListenMedia | null, audioB: ListenMedia | null): void {
  useEffect(() => {
    if (!audioA || !audioB) return;
    const record = useListenStore.getState().record;
    const detachA = attachListenTracker(audioA, 'A', record);
    const detachB = attachListenTracker(audioB, 'B', record);
    return () => {
      detachA();
      detachB();
    };
  }, [audioA, audioB]);
}
