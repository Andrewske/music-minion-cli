import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAudioPlayer } from './useAudioPlayer';

// Mock the comparison store
vi.mock('../stores/comparisonStore', () => ({
  useComparisonStore: vi.fn(),
}));

import { useComparisonStore } from '../stores/comparisonStore';

describe('useAudioPlayer', () => {
  const mockSetPlaying = vi.fn();
  const mockUseComparisonStore = useComparisonStore as any;

  const mockTrackA = {
    id: 1,
    title: 'Track A',
    artist: 'Artist A',
    album: 'Album A',
    duration: 180,
    year: 2023,
    rating: 1500,
    comparison_count: 10,
    wins: 6,
    losses: 4,
    has_waveform: true,
  };

  const mockTrackB = {
    id: 2,
    title: 'Track B',
    artist: 'Artist B',
    album: 'Album B',
    duration: 200,
    year: 2023,
    rating: 1400,
    comparison_count: 8,
    wins: 4,
    losses: 4,
    has_waveform: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseComparisonStore.mockReturnValue({
      playingTrack: null,
      setPlaying: mockSetPlaying,
    });
  });

  it('returns correct playing state when track matches playing track', () => {
    mockUseComparisonStore.mockReturnValue({
      playingTrack: mockTrackA,
      setPlaying: mockSetPlaying,
    });

    const { result } = renderHook(() => useAudioPlayer(mockTrackA, false));

    expect(result.current.isPlaying).toBe(true);
  });

  it('returns false playing state when track does not match playing track', () => {
    mockUseComparisonStore.mockReturnValue({
      playingTrack: mockTrackA,
      setPlaying: mockSetPlaying,
    });

    const { result } = renderHook(() => useAudioPlayer(mockTrackB, false));

    expect(result.current.isPlaying).toBe(false);
  });

  it('calls setPlaying with track when playTrack is called', () => {
    const { result } = renderHook(() => useAudioPlayer(mockTrackA, false));

    act(() => {
      result.current.playTrack(mockTrackB);
    });

    expect(mockSetPlaying).toHaveBeenCalledWith(mockTrackB);
  });

  it('calls setPlaying with null when pauseTrack is called', () => {
    const { result } = renderHook(() => useAudioPlayer(mockTrackA, false));

    act(() => {
      result.current.pauseTrack();
    });

    expect(mockSetPlaying).toHaveBeenCalledWith(null);
  });

  it('allows seamless switching in comparison mode', () => {
    // In comparison mode, the useEffect that would pause tracks when another starts
    // should be skipped. We can't directly test the useEffect logic without
    // more complex mocking, but we can verify the hook works correctly in comparison mode.

    mockUseComparisonStore.mockReturnValue({
      playingTrack: mockTrackA,
      setPlaying: mockSetPlaying,
    });

    const { result } = renderHook(() => useAudioPlayer(mockTrackA, true));

    // Verify basic functionality still works in comparison mode
    expect(result.current.isPlaying).toBe(true);

    act(() => {
      result.current.playTrack(mockTrackB);
    });

    expect(mockSetPlaying).toHaveBeenCalledWith(mockTrackB);
  });

  it('handles null track correctly', () => {
    mockUseComparisonStore.mockReturnValue({
      playingTrack: mockTrackA,
      setPlaying: mockSetPlaying,
    });

    const { result } = renderHook(() => useAudioPlayer(null, false));

    expect(result.current.isPlaying).toBe(false);
  });
});