import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { usePlayer } from './usePlayer';
import { usePlayerStore } from '../stores/playerStore';
import { AudioElementProvider } from '../contexts/AudioElementContext';

// Mock fetch so store actions don't make real network calls
const mockFetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response),
);
vi.stubGlobal('fetch', mockFetch);

// Patch HTMLMediaElement methods (jsdom's defaults are noops or throw)
const playMock = vi.fn(() => Promise.resolve());
const pauseMock = vi.fn();
const loadMock = vi.fn();

beforeEach(() => {
  playMock.mockClear();
  pauseMock.mockClear();
  loadMock.mockClear();
  mockFetch.mockClear();

  HTMLMediaElement.prototype.play = playMock;
  HTMLMediaElement.prototype.pause = pauseMock;
  HTMLMediaElement.prototype.load = loadMock;

  // Reset store to initial state for isolation between tests
  usePlayerStore.setState({
    currentTrack: null,
    queue: [],
    queueIndex: 0,
    isPlaying: false,
    isThisDeviceActive: true,
    volume: 1.0,
    isMuted: false,
    currentContext: null,
    positionMs: 0,
    trackStartedAt: null,
    scrobbledThisPlaythrough: false,
    lastSeekAt: 0,
    activeDeviceId: 'test-device-123',
    playbackError: null,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const wrapper = ({ children }: { children: ReactNode }): JSX.Element => (
  <AudioElementProvider>{children}</AudioElementProvider>
);

const TRACK_A = { id: 1, title: 'Track A', artist: 'A', file_path: null, duration: 180 } as any;
const TRACK_B = { id: 2, title: 'Track B', artist: 'B', file_path: null, duration: 200 } as any;
const TRACK_C = { id: 3, title: 'Track C', artist: 'C', file_path: null, duration: 220 } as any;

function getAudioElements(): [HTMLAudioElement, HTMLAudioElement] {
  const els = Array.from(document.querySelectorAll('audio')) as HTMLAudioElement[];
  if (els.length !== 2) {
    throw new Error(`expected 2 audio elements, got ${els.length}`);
  }
  return [els[0], els[1]];
}

function setReadyState(el: HTMLAudioElement, value: number): void {
  Object.defineProperty(el, 'readyState', { value, configurable: true });
}

describe('usePlayer dual-element swap', () => {
  it('1. fast-swap: when inactive is preloaded and ready, swap without binding new src', () => {
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [a, b] = getAudioElements();

    // Capture canplay handler so we can trigger the swap manually (jsdom won't fire canplay)
    const captured: { handler: (() => void) | null } = { handler: null };
    const realAdd = b.addEventListener.bind(b);
    vi.spyOn(b, 'addEventListener').mockImplementation((event, handler, options) => {
      if (event === 'canplay' && !captured.handler) {
        captured.handler = handler as () => void;
      } else {
        realAdd(event, handler, options);
      }
    });

    // Step 1: load-on-swap from cold (current=A on element A, loads B for track A)
    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_A, isPlaying: true });
    });
    // Manually trigger canplay to flip activeKey to 'B'. Now element B serves TRACK_A.
    act(() => {
      captured.handler?.();
    });

    // Step 2: simulate preload of TRACK_B onto element A (the now-inactive element)
    a.dataset.trackId = String(TRACK_B.id);
    setReadyState(a, 4);

    const setSrcOnASpy = vi.spyOn(a, 'src', 'set');
    playMock.mockClear();

    // Step 3: track change to TRACK_B. Should fast-swap onto A without rebinding src.
    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_B });
    });

    // No new src binding on A (fast-swap path, A was already preloaded)
    expect(setSrcOnASpy).not.toHaveBeenCalled();

    // A.play() called because isPlaying is true
    expect(playMock).toHaveBeenCalled();
  });

  it('2. load-on-swap REGRESSION: pause+removeAttribute+load called BEFORE new src binding (silence guarantee)', () => {
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [a, b] = getAudioElements();
    const callOrder: string[] = [];

    const aPauseSpy = vi.spyOn(a, 'pause').mockImplementation(() => {
      callOrder.push('a.pause');
    });
    const aRemoveSpy = vi.spyOn(a, 'removeAttribute').mockImplementation(() => {
      callOrder.push('a.removeAttribute');
    });
    const aLoadSpy = vi.spyOn(a, 'load').mockImplementation(() => {
      callOrder.push('a.load');
    });
    vi.spyOn(b, 'src', 'set').mockImplementation(() => {
      callOrder.push('b.src=');
    });
    const addEventListenerSpy = vi.spyOn(b, 'addEventListener').mockImplementation(() => {
      callOrder.push('b.addEventListener');
    });

    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_A, isPlaying: true });
    });
    callOrder.length = 0;
    aPauseSpy.mockClear();
    aRemoveSpy.mockClear();
    aLoadSpy.mockClear();

    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_B });
    });

    // Silence sequence first
    expect(callOrder.indexOf('a.pause')).toBeLessThan(callOrder.indexOf('a.removeAttribute'));
    expect(callOrder.indexOf('a.removeAttribute')).toBeLessThan(callOrder.indexOf('a.load'));
    // Then new src binding on b
    expect(callOrder.indexOf('a.load')).toBeLessThan(callOrder.indexOf('b.src='));

    // canplay listener registered
    const canplayCall = addEventListenerSpy.mock.calls.find((c) => c[0] === 'canplay');
    expect(canplayCall).toBeDefined();
    // Third arg is options object with signal
    expect(canplayCall?.[2]).toMatchObject({ once: true });
    expect((canplayCall?.[2] as AddEventListenerOptions).signal).toBeInstanceOf(AbortSignal);
  });

  it('3. rapid skip aborts in-flight canplay listener', () => {
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();
    const captured: { firstSignal: AbortSignal | null } = { firstSignal: null };

    vi.spyOn(b, 'addEventListener').mockImplementation((event, _handler, options) => {
      if (
        event === 'canplay'
        && options
        && typeof options === 'object'
        && !captured.firstSignal
      ) {
        captured.firstSignal = (options as AddEventListenerOptions).signal ?? null;
      }
    });

    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_A, isPlaying: true });
    });

    expect(captured.firstSignal).not.toBeNull();
    expect(captured.firstSignal?.aborted).toBe(false);

    // Rapid skip to a different track before canplay fires
    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_B });
    });

    // First effect's controller was aborted by cleanup
    expect(captured.firstSignal?.aborted).toBe(true);
  });

  it('4. preload binds inactive element to queue[queueIndex+1] after debounce', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();

    act(() => {
      usePlayerStore.setState({
        currentTrack: TRACK_A,
        queue: [TRACK_A, TRACK_B, TRACK_C],
        queueIndex: 0,
        isPlaying: true,
      });
    });

    // Before debounce fires, inactive should not yet be bound to TRACK_B
    expect(b.dataset.trackId).not.toBe(String(TRACK_B.id));

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(b.dataset.trackId).toBe(String(TRACK_B.id));
    expect(b.getAttribute('src')).toContain(`/api/tracks/${TRACK_B.id}/stream`);
  });

  it('5. preload skipped in comparison mode (no preload of next-track)', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();

    act(() => {
      usePlayerStore.setState({
        currentTrack: TRACK_A,
        queue: [TRACK_A, TRACK_B, TRACK_C],
        queueIndex: 0,
        currentContext: { type: 'comparison' },
      });
    });

    act(() => {
      vi.advanceTimersByTime(600);
    });

    // Track-change handler may have set b.dataset.trackId to TRACK_A.id during initial swap,
    // but the preload effect must NOT have bound it to TRACK_B.id (the queue's next track).
    expect(b.dataset.trackId).not.toBe(String(TRACK_B.id));
  });

  it('6. preload debounce: rapid currentTrack changes fire single preload binding', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();
    const setSrcSpy = vi.spyOn(b, 'src', 'set');

    act(() => {
      usePlayerStore.setState({
        currentTrack: TRACK_A,
        queue: [TRACK_A, TRACK_B, TRACK_C],
        queueIndex: 0,
      });
    });
    setSrcSpy.mockClear();

    // Rapid skips within debounce window
    for (let i = 0; i < 5; i += 1) {
      act(() => {
        usePlayerStore.setState({ queueIndex: i });
      });
      act(() => {
        vi.advanceTimersByTime(50);
      });
    }

    setSrcSpy.mockClear();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    // Only one binding fired after the debounce settles
    expect(setSrcSpy.mock.calls.length).toBeLessThanOrEqual(1);
  });

  it('7. volume/mute apply to both audio elements', () => {
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [a, b] = getAudioElements();

    act(() => {
      usePlayerStore.setState({ volume: 0.5 });
    });
    expect(a.volume).toBe(0.5);
    expect(b.volume).toBe(0.5);

    act(() => {
      usePlayerStore.setState({ isMuted: true });
    });
    expect(a.muted).toBe(true);
    expect(b.muted).toBe(true);
  });

  it('8. circuit breaker: 3 errors within 10s stops auto-skip cascade; canplay resets', () => {
    vi.useFakeTimers();
    const nextSpy = vi.fn(() => Promise.resolve());
    usePlayerStore.setState({ next: nextSpy });

    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_A, isPlaying: true });
    });

    const [a] = getAudioElements();

    // Fire 3 errors in quick succession
    act(() => {
      a.dispatchEvent(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(nextSpy).toHaveBeenCalledTimes(1);

    act(() => {
      a.dispatchEvent(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(nextSpy).toHaveBeenCalledTimes(2);

    nextSpy.mockClear();
    act(() => {
      a.dispatchEvent(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    // Third error trips breaker — no auto-skip
    expect(nextSpy).not.toHaveBeenCalled();
    expect(usePlayerStore.getState().playbackError).toMatch(/Playback unavailable/);

    // canplay resets the window
    act(() => {
      a.dispatchEvent(new Event('canplay'));
    });
    act(() => {
      a.dispatchEvent(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    // After reset, first error in fresh window auto-skips again
    expect(nextSpy).toHaveBeenCalledTimes(1);
  });

  it('9. preload error clears inactive.dataset.trackId', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();

    act(() => {
      usePlayerStore.setState({
        currentTrack: TRACK_A,
        queue: [TRACK_A, TRACK_B, TRACK_C],
        queueIndex: 0,
      });
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(b.dataset.trackId).toBe(String(TRACK_B.id));

    act(() => {
      b.dispatchEvent(new Event('error'));
    });

    expect(b.dataset.trackId).toBeUndefined();
  });

  it('10. canplay handler reads isPlaying at fire time, not effect-run time', () => {
    const { result } = renderHook(() => usePlayer(), { wrapper });
    void result;

    const [, b] = getAudioElements();
    const captured: { handler: (() => void) | null } = { handler: null };

    vi.spyOn(b, 'addEventListener').mockImplementation((event, handler) => {
      if (event === 'canplay') {
        captured.handler = handler as () => void;
      }
    });

    // Effect runs with isPlaying = true
    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_A, isPlaying: true });
    });
    act(() => {
      usePlayerStore.setState({ currentTrack: TRACK_B });
    });
    expect(captured.handler).not.toBeNull();

    // User pauses BEFORE canplay fires
    act(() => {
      usePlayerStore.setState({ isPlaying: false });
    });

    playMock.mockClear();

    // Now fire canplay
    act(() => {
      captured.handler?.();
    });

    // play() should NOT have been called because isPlaying is false at fire time
    expect(playMock).not.toHaveBeenCalled();
  });

  it('11. circuit breaker errorTimes is per-hook-instance (useRef isolation)', () => {
    vi.useFakeTimers();
    const nextSpy = vi.fn(() => Promise.resolve());
    usePlayerStore.setState({ next: nextSpy, currentTrack: TRACK_A, isPlaying: true });

    // First instance: trip the breaker
    const { unmount: unmount1 } = renderHook(() => usePlayer(), { wrapper });
    let [a1] = getAudioElements();

    for (let i = 0; i < 3; i += 1) {
      act(() => {
        a1.dispatchEvent(new Event('error'));
      });
      act(() => {
        vi.advanceTimersByTime(600);
      });
    }
    // Breaker tripped
    expect(usePlayerStore.getState().playbackError).toMatch(/Playback unavailable/);

    unmount1();
    nextSpy.mockClear();
    usePlayerStore.setState({ playbackError: null });

    // Second instance: should start with empty errorTimes
    renderHook(() => usePlayer(), { wrapper });
    [a1] = getAudioElements();

    // Single error in fresh instance triggers auto-skip (breaker has not tripped)
    act(() => {
      a1.dispatchEvent(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(nextSpy).toHaveBeenCalledTimes(1);
  });
});
