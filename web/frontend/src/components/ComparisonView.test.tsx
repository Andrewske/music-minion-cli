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

import { useComparisonStore } from '../stores/comparisonStore';
import { useStartSession, useRecordComparison, useArchiveTrack } from '../hooks/useComparison';
import { useAudioPlayer } from '../hooks/useAudioPlayer';

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
});