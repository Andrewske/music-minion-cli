import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { FeedWaveform } from './FeedWaveform';

vi.mock('../../api/tracks', () => ({ getWaveformData: vi.fn(async () => ({ peaks: [] })) }));
vi.mock('../../stores/playerStore', async () => {
  const { create } = await import('zustand');
  const usePlayerStore = create(() => ({ currentTrack: null, seek: vi.fn(async () => undefined) }));
  return { usePlayerStore, getCurrentPosition: () => 0 };
});

function renderWaveform(props: Parameters<typeof FeedWaveform>[0]): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FeedWaveform {...props} />
    </QueryClientProvider>
  );
}

describe('FeedWaveform', () => {
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
