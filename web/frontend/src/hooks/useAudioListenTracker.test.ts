import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  attachListenTracker,
  attachStoreSeekTracker,
  useAudioListenTracker,
  type ListenMedia,
} from './useAudioListenTracker';
import { seekAudio } from '../lib/audioSource';
import { INITIAL_LISTEN_STATE } from '../lib/feedListen';
import { usePlayerStore } from '../stores/playerStore';
import type { Track } from '@music-minion/shared';
import { getListenStats, getPlayedListenStats, useListenStore } from '../stores/listenStore';

type FakeAudio = ListenMedia & {
  fire: (type: string, positionMs: number) => void;
  dispatchEvent: (event: Event) => boolean;
};

function fakeAudio(trackId?: number): FakeAudio {
  const target = new EventTarget();
  const el = {
    currentTime: 0,
    dataset: trackId === undefined ? {} : { trackId: String(trackId) },
    addEventListener: target.addEventListener.bind(target),
    removeEventListener: target.removeEventListener.bind(target),
    dispatchEvent: target.dispatchEvent.bind(target),
    fire: (type: string, positionMs: number): void => {
      el.currentTime = positionMs / 1000;
      target.dispatchEvent(new Event(type));
    },
  };
  return el as FakeAudio;
}

beforeEach(() => {
  useListenStore.setState(INITIAL_LISTEN_STATE);
});

describe('audio listen tracker', () => {
  it('counts nothing when autoplay is blocked or the stream is buffering', () => {
    const audio = fakeAudio(1);
    const detach = attachListenTracker(audio, 'A', useListenStore.getState().record);
    // Blocked autoplay: play() rejected, the element emits no progress at all.
    expect(getPlayedListenStats(1)).toBeUndefined();
    // Buffering: waiting/stalled fire, timeupdate repeats the same position.
    audio.fire('timeupdate', 4_000);
    audio.fire('waiting', 4_000);
    audio.fire('stalled', 4_000);
    audio.fire('timeupdate', 4_000);
    expect(getListenStats(1).listenSeconds).toBe(0);
    detach();
  });

  it('records the furthest point across a forward-and-back seek', () => {
    const audio = fakeAudio(1);
    const detach = attachListenTracker(audio, 'A', useListenStore.getState().record);
    audio.fire('timeupdate', 0);
    audio.fire('timeupdate', 1_000);
    audio.fire('seeking', 150_000);
    audio.fire('seeking', 20_000);
    audio.fire('seeked', 20_000);
    audio.fire('timeupdate', 20_500);
    expect(getListenStats(1)).toEqual({ listenSeconds: 1.5, maxPositionMs: 150_000 });
    detach();
  });

  it('keeps the furthest target when two seeks land before the browser events fire', () => {
    const audio = fakeAudio(1);
    const detach = attachListenTracker(audio, 'A', useListenStore.getState().record);
    audio.fire('timeupdate', 0);
    // A real element reads back the latest target in its queued seeking/seeked events.
    seekAudio(audio as unknown as HTMLAudioElement, 150);
    seekAudio(audio as unknown as HTMLAudioElement, 20);
    audio.fire('seeking', 20_000);
    audio.fire('seeked', 20_000);
    expect(getListenStats(1)).toEqual({ listenSeconds: 0, maxPositionMs: 150_000 });
    detach();
  });

  it('records store seeks that React batches into one audio seek', () => {
    usePlayerStore.setState({
      currentTrack: { id: 7 } as Track,
      isAudioLeader: true,
      isPlaying: false,
      lastSeekAt: 0,
    });
    const detach = attachStoreSeekTracker(useListenStore.getState().record);
    usePlayerStore.setState({ positionMs: 150_000, lastSeekAt: 1 });
    usePlayerStore.setState({ positionMs: 20_000, lastSeekAt: 2 });
    expect(getListenStats(7)).toEqual({ listenSeconds: 0, maxPositionMs: 150_000 });
    detach();
    usePlayerStore.setState({ currentTrack: null, lastSeekAt: 0 });
  });

  it('ignores elements with no bound track', () => {
    const audio = fakeAudio();
    const detach = attachListenTracker(audio, 'A', useListenStore.getState().record);
    audio.fire('timeupdate', 1_000);
    expect(useListenStore.getState().tallies).toEqual({});
    detach();
  });

  it('keeps the tally after a page that read it unmounts, since the player owns it', () => {
    const audioA = fakeAudio(5);
    const audioB = fakeAudio();
    const player = renderHook(() => useAudioListenTracker(audioA, audioB));
    // A feed page that reads stats mounts, reads, and navigates away.
    const feed = renderHook(() => getListenStats(5));
    audioA.fire('timeupdate', 0);
    audioA.fire('timeupdate', 2_000);
    feed.unmount();
    audioA.fire('timeupdate', 4_000);
    expect(getListenStats(5)).toEqual({ listenSeconds: 4, maxPositionMs: 4_000 });
    player.unmount();
    audioA.fire('timeupdate', 6_000);
    expect(getListenStats(5).listenSeconds).toBe(4);
  });
});
