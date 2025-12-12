import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useWavesurfer } from './useWavesurfer';

// Mock WaveSurfer
vi.mock('wavesurfer.js', () => ({
  default: {
    create: vi.fn(),
  },
}));

// Mock API functions
vi.mock('../api/tracks', () => ({
  getWaveformData: vi.fn(),
  getStreamUrl: vi.fn(),
}));

import WaveSurfer from 'wavesurfer.js';
import { getWaveformData, getStreamUrl } from '../api/tracks';

describe('useWavesurfer', () => {
  let mockWaveSurfer: any;
  let capturedHandlers: Record<string, any>;

  beforeEach(() => {
    vi.clearAllMocks();
    capturedHandlers = {};

    mockWaveSurfer = {
      load: vi.fn(),
      destroy: vi.fn(),
      play: vi.fn(),
      pause: vi.fn(),
      seekTo: vi.fn(),
      playPause: vi.fn(),
      getDuration: vi.fn(() => 180),
      getCurrentTime: vi.fn(() => 0),
      isPlaying: vi.fn(() => false),
      on: vi.fn((event: string, handler: any) => {
        capturedHandlers[event] = handler;
      }),
      off: vi.fn(),
    };

    (WaveSurfer.create as any).mockReturnValue(mockWaveSurfer);
    (getWaveformData as any).mockResolvedValue({ peaks: [0.1, 0.2, 0.3] });
    (getStreamUrl as any).mockReturnValue('http://example.com/audio.mp3');
  });

  it('can be instantiated with onFinish callback', () => {
    const onFinish = vi.fn();

    // Render the hook
    const { result } = renderHook(() =>
      useWavesurfer({
        trackId: 1,
        onFinish,
        isActive: false, // Don't try to initialize WaveSurfer
      })
    );

    // Verify the hook returns the expected interface
    expect(result.current).toHaveProperty('containerRef');
    expect(result.current).toHaveProperty('isPlaying');
    expect(result.current).toHaveProperty('currentTime');
    expect(result.current).toHaveProperty('duration');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('retryLoad');
    expect(result.current).toHaveProperty('seekToPercent');
    expect(result.current).toHaveProperty('togglePlayPause');
  });

  it('handles onFinish callback parameter', () => {
    const onFinish = vi.fn();

    // Render the hook with onFinish
    renderHook(() =>
      useWavesurfer({
        trackId: 1,
        onFinish,
        isActive: false,
      })
    );

    // The test passes if the hook can be rendered with onFinish without errors
    expect(onFinish).not.toHaveBeenCalled(); // Should not be called during setup
  });

  it('calls onFinish when audio playback completes', async () => {
    const onFinish = vi.fn();

    const { result, rerender } = renderHook(
      ({ trackId }) =>
        useWavesurfer({
          trackId,
          onFinish,
          isActive: true,
        }),
      { initialProps: { trackId: 1 } }
    );

    // Set up container and trigger initialization
    const container = document.createElement('div');
    (result.current.containerRef as any).current = container;
    rerender({ trackId: 2 });

    // Wait for initialization
    await vi.waitFor(() => {
      expect(capturedHandlers.finish).toBeDefined();
    });

    // Simulate wavesurfer finish event
    capturedHandlers.finish();

    // Verify onFinish was called
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it('debounces rapid finish events with 2 second cooldown', async () => {
    const onFinish = vi.fn();

    const { result, rerender } = renderHook(
      ({ trackId }) =>
        useWavesurfer({
          trackId,
          onFinish,
          isActive: true,
        }),
      { initialProps: { trackId: 1 } }
    );

    // Set up container and trigger initialization
    const container = document.createElement('div');
    (result.current.containerRef as any).current = container;
    rerender({ trackId: 2 });

    // Wait for initialization
    await vi.waitFor(() => {
      expect(capturedHandlers.finish).toBeDefined();
    });

    vi.useFakeTimers();

    // First finish event - should trigger
    capturedHandlers.finish();
    expect(onFinish).toHaveBeenCalledTimes(1);

    // Second finish event immediately after - should be debounced
    capturedHandlers.finish();
    expect(onFinish).toHaveBeenCalledTimes(1); // Still 1

    // Advance time by 1 second - still within debounce window
    vi.advanceTimersByTime(1000);
    capturedHandlers.finish();
    expect(onFinish).toHaveBeenCalledTimes(1); // Still 1

    // Advance time by another 1.5 seconds (total 2.5s) - outside debounce window
    vi.advanceTimersByTime(1500);
    capturedHandlers.finish();
    expect(onFinish).toHaveBeenCalledTimes(2); // Now 2

    vi.useRealTimers();
  });
});