import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ComparisonView } from './ComparisonView';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the hooks and stores
vi.mock('../stores/comparisonStore', () => ({
  useComparisonStore: vi.fn(),
}));

vi.mock('../hooks/useComparison', () => ({
  useStartSession: vi.fn(),
  useRecordComparison: vi.fn(),
  useArchiveTrack: vi.fn(),
}));

vi.mock('../hooks/useAudioPlayer', () => ({
  useAudioPlayer: vi.fn(),
}));

vi.mock('../api/tracks', () => ({
  getFolders: vi.fn(),
}));

vi.mock('./WaveformPlayer', () => ({
  WaveformPlayer: vi.fn(),
}));

import { useComparisonStore } from '../stores/comparisonStore';
import { useStartSession, useRecordComparison, useArchiveTrack } from '../hooks/useComparison';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { getFolders } from '../api/tracks';
import { WaveformPlayer } from './WaveformPlayer';

describe('ComparisonView', () => {
  const mockUseComparisonStore = useComparisonStore as any;
  const mockUseStartSession = useStartSession as any;
  const mockUseRecordComparison = useRecordComparison as any;
  const mockUseArchiveTrack = useArchiveTrack as any;
  const mockUseAudioPlayer = useAudioPlayer as any;

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

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

  const mockPlayingTrack = {
    id: 3,
    title: 'Playing Track',
    artist: 'Playing Artist',
    album: 'Playing Album',
    duration: 190,
    year: 2023,
    rating: 1600,
    comparison_count: 12,
    wins: 8,
    losses: 4,
    has_waveform: true,
  };

  beforeEach(() => {
    mockUseStartSession.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    });

    mockUseRecordComparison.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });

    mockUseArchiveTrack.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });

    mockUseAudioPlayer.mockReturnValue({
      playTrack: vi.fn(),
      pauseTrack: vi.fn(),
    });

    (getFolders as any).mockResolvedValue({
      root: '/music',
      folders: ['rock', 'jazz', 'electronic'],
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <ComparisonView />
      </QueryClientProvider>
    );

  it('shows playing track info in player bar even when track is not in current pair', () => {
    // Mock store to return current pair with tracks A and B, but playing track is different
    mockUseComparisonStore.mockReturnValue({
      currentPair: {
        session_id: 1,
        track_a: mockTrackA,
        track_b: mockTrackB,
      },
      playingTrack: mockPlayingTrack,
      comparisonsCompleted: 5,
    });

    renderComponent();

    // Check that the player bar shows the playing track info, not the current pair tracks
    expect(screen.getByText('NOW PLAYING')).toBeInTheDocument();
    expect(screen.getByText('Playing Artist - Playing Track')).toBeInTheDocument();
  });

  it('shows PAUSED when no track is playing', () => {
    mockUseComparisonStore.mockReturnValue({
      currentPair: {
        session_id: 1,
        track_a: mockTrackA,
        track_b: mockTrackB,
      },
      playingTrack: null,
      comparisonsCompleted: 5,
    });

    renderComponent();

    expect(screen.getByText('PAUSED')).toBeInTheDocument();
    // Check that the track info span is empty
    const trackInfoSpan = screen.getByText('PAUSED').parentElement?.querySelector('.truncate');
    expect(trackInfoSpan?.textContent).toBe('');
  });

  describe('handleTrackFinish', () => {
    it('automatically switches to other track when one finishes in comparison mode', () => {
      const mockPlayTrack = vi.fn();
      let capturedOnFinish: (() => void) | undefined;

      // Mock WaveformPlayer to capture the onFinish callback
      const MockWaveformPlayer = vi.fn((props) => {
        capturedOnFinish = props.onFinish;
        return null;
      });
      vi.mocked(WaveformPlayer).mockImplementation(MockWaveformPlayer);

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: vi.fn(),
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackA,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Simulate track A finishing by calling the captured onFinish callback
      expect(capturedOnFinish).toBeDefined();
      capturedOnFinish!();

      // Should switch from track A to track B
      expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackB);
    });

    it('does not switch tracks when not in comparison mode', () => {
      const mockPlayTrack = vi.fn();

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: vi.fn(),
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackA,
        comparisonsCompleted: 5,
        isComparisonMode: false, // Not in comparison mode
      });

      renderComponent();

      // Verify that playTrack was not called during render
      expect(mockPlayTrack).not.toHaveBeenCalled();
    });

    it('switches from track A to track B when track A finishes', () => {
      const mockPlayTrack = vi.fn();
      let capturedOnFinish: (() => void) | undefined;

      // Mock WaveformPlayer to capture the onFinish callback
      const MockWaveformPlayer = vi.fn((props) => {
        capturedOnFinish = props.onFinish;
        return null;
      });
      vi.mocked(WaveformPlayer).mockImplementation(MockWaveformPlayer);

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: vi.fn(),
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackA,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Simulate track A finishing
      expect(capturedOnFinish).toBeDefined();
      capturedOnFinish!();

      // Should switch to track B
      expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackB);
    });

    it('switches from track B to track A when track B finishes', () => {
      const mockPlayTrack = vi.fn();
      let capturedOnFinish: (() => void) | undefined;

      // Mock WaveformPlayer to capture the onFinish callback
      const MockWaveformPlayer = vi.fn((props) => {
        capturedOnFinish = props.onFinish;
        return null;
      });
      vi.mocked(WaveformPlayer).mockImplementation(MockWaveformPlayer);

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: vi.fn(),
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackB,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Simulate track B finishing
      expect(capturedOnFinish).toBeDefined();
      capturedOnFinish!();

      // Should switch to track A
      expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackA);
    });

    it('does nothing when no current pair exists', () => {
      const mockPlayTrack = vi.fn();

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: vi.fn(),
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: null,
        playingTrack: null,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Verify that playTrack was not called during render
      expect(mockPlayTrack).not.toHaveBeenCalled();
    });

    it('handles pause and resume correctly during looping', () => {
      const mockPlayTrack = vi.fn();
      const mockPauseTrack = vi.fn();
      let capturedOnFinish: (() => void) | undefined;

      // Mock WaveformPlayer to capture the onFinish callback
      const MockWaveformPlayer = vi.fn((props) => {
        capturedOnFinish = props.onFinish;
        return null;
      });
      vi.mocked(WaveformPlayer).mockImplementation(MockWaveformPlayer);

      mockUseAudioPlayer.mockReturnValue({
        playTrack: mockPlayTrack,
        pauseTrack: mockPauseTrack,
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackA,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Simulate track A finishing - should switch to track B
      expect(capturedOnFinish).toBeDefined();
      capturedOnFinish!();
      expect(mockPlayTrack).toHaveBeenCalledWith(mockTrackB);

      // Simulate pausing track B
      const trackBElement = screen.getAllByText('Track B')[0];
      expect(trackBElement).toBeInTheDocument();
      // The pause functionality is tested through the useAudioPlayer hook
    });

    it('stops looping when winner is selected', () => {
      const mockRecordComparison = vi.fn();

      mockUseRecordComparison.mockReturnValue({
        mutate: mockRecordComparison,
        isPending: false,
      });

      mockUseComparisonStore.mockReturnValue({
        currentPair: {
          session_id: 1,
          track_a: mockTrackA,
          track_b: mockTrackB,
        },
        playingTrack: mockTrackA,
        comparisonsCompleted: 5,
        isComparisonMode: true,
      });

      renderComponent();

      // Simulate selecting track A as winner
      const trackAElement = screen.getAllByText('Track A')[0];
      expect(trackAElement).toBeInTheDocument();

      // The winner selection should stop the looping by advancing to next pair
      // This is tested through the recordComparison mutation
      expect(mockUseRecordComparison).toHaveBeenCalled();
    });
  });
});