import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Backdrop } from './TrackBannerParts';

const imgSrc = (container: HTMLElement): string | null =>
  container.querySelector('img')?.getAttribute('src') ?? null;

describe('Backdrop artwork', () => {
  it('upsizes stored SoundCloud artwork', () => {
    const { container } = render(
      <Backdrop trackId={7} artworkUrl="https://i1.sndcdn.com/a-large.jpg" title="T" />,
    );
    expect(imgSrc(container)).toBe('https://i1.sndcdn.com/a-t500x500.jpg');
  });

  it('falls back to embedded art when no artwork_url is stored', () => {
    const { container } = render(<Backdrop trackId={7} title="T" />);
    expect(imgSrc(container)).toBe('/api/tracks/7/artwork');
  });

  it('shows the gradient when the image fails, and retries for the next track', () => {
    const { container, rerender } = render(<Backdrop trackId={7} title="T" />);
    fireEvent.error(container.querySelector('img')!);
    expect(container.querySelector('img')).toBeNull();

    rerender(<Backdrop trackId={8} title="T" />);
    expect(imgSrc(container)).toBe('/api/tracks/8/artwork');
  });
});
