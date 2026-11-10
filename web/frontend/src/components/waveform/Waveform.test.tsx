import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { Waveform } from './Waveform';
import { barCountFor, downsamplePeaks } from './waveformBars';

vi.mock('../../api/tracks', () => ({
  getWaveformData: vi.fn(async () => ({ peaks: [] })),
  waveformQueryKey: (id: number | null) => ['waveform', id],
}));
vi.mock('../../stores/playerStore', async () => {
  const { create } = await import('zustand');
  const usePlayerStore = create(() => ({ currentTrack: null, seek: vi.fn(async () => undefined) }));
  return { usePlayerStore, getCurrentPosition: () => 0 };
});

function renderWaveform(props: Parameters<typeof Waveform>[0]): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Waveform {...props} />
    </QueryClientProvider>
  );
}

describe('Waveform', () => {
  it('starts a track that has no library id yet', () => {
    const onActivate = vi.fn();
    renderWaveform({ localTrackId: null, durationMs: 200_000, onActivate });
    fireEvent.click(screen.getByRole('button', { name: 'Play from here' }));
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it('starts it from the keyboard too', () => {
    const onActivate = vi.fn();
    renderWaveform({ localTrackId: null, durationMs: 200_000, onActivate });
    fireEvent.keyDown(screen.getByRole('button', { name: 'Play from here' }), { key: 'Enter' });
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it('stays inert without a handler or a library id', () => {
    renderWaveform({ localTrackId: null, durationMs: 200_000 });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

describe('downsamplePeaks', () => {
  it('returns one bar per requested slot', () => {
    expect(downsamplePeaks([-1, 1, -2, 2, -3, 3, -4, 4], 4)).toHaveLength(4);
    expect(downsamplePeaks([], 4)).toEqual([]);
  });

  it('stretches a near-full-scale track so quiet and loud parts differ', () => {
    const quiet = Array.from({ length: 50 }, () => 0.8);
    const loud = Array.from({ length: 50 }, () => 1);
    const bars = downsamplePeaks([...quiet, ...loud], 10);
    expect(bars[0]).toBeLessThan(0.5);
    expect(bars[9]).toBe(1);
  });

  it('fills a flat signal instead of dividing by zero', () => {
    expect(downsamplePeaks([0.5, 0.5, 0.5, 0.5], 2)).toEqual([1, 1]);
  });
});

describe('barCountFor', () => {
  it('packs a bar every 3px', () => {
    expect(barCountFor(600)).toBe(200);
    expect(barCountFor(0)).toBe(1);
  });
});
