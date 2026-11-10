import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { WaveformPlayer } from './WaveformPlayer';

const audio = document.createElement('audio');

vi.mock('./waveform/Waveform', () => ({ Waveform: () => <div data-testid="waveform" /> }));
vi.mock('../api/tracks', () => ({ refreshWaveform: vi.fn(), waveformQueryKey: (id: number) => ['waveform', id] }));
vi.mock('../contexts/AudioElementContext', () => ({ useActiveAudioElement: () => audio }));
vi.mock('../stores/playerStore', async () => {
  const { create } = await import('zustand');
  const usePlayerStore = create(() => ({ currentTrack: { id: 1 }, positionMs: 0, isPlaying: false }));
  return { usePlayerStore, getCurrentPosition: () => 0 };
});

function renderPlayer(trackId: number, onFinish: () => void): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WaveformPlayer track={{ id: trackId, title: 'T', duration: 180 }} isPlaying onTogglePlayPause={vi.fn()} onFinish={onFinish} />
    </QueryClientProvider>
  );
}

describe('WaveformPlayer', () => {
  it('calls onFinish when the current track ends', () => {
    const onFinish = vi.fn();
    renderPlayer(1, onFinish);
    audio.dispatchEvent(new Event('ended'));
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it('ignores the end of a track it is not showing', () => {
    const onFinish = vi.fn();
    renderPlayer(2, onFinish);
    audio.dispatchEvent(new Event('ended'));
    expect(onFinish).not.toHaveBeenCalled();
  });
});
