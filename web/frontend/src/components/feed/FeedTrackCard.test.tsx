import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import type { FeedItem } from '../../api/feed';
import { FeedTrackCard } from './FeedTrackCard';

vi.mock('./FeedWaveform', () => ({
  FeedWaveform: () => <div data-testid="waveform" />,
}));
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/artist">{children}</a>,
}));
vi.mock('./ArtistHoverCard', () => ({
  ArtistHoverCard: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const makeItem = (overrides: Partial<FeedItem> = {}): FeedItem => ({
  id: '42',
  soundcloud_id: '42',
  local_track_id: 7,
  title: 'Signal Path',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 125_000,
  genre: 'Bass',
  access: 'playable',
  event_at: '2026-09-12T00:00:00Z',
  uploaded_at: '2026-09-10T00:00:00Z',
  released_at: '2026-09-10T00:00:00Z',
  sources: ['release', 'repost'],
  uploader: {
    id: 1,
    soundcloud_id: 'original-sc',
    display_name: 'Original Artist',
    slug: 'original',
    avatar_url: null,
    ranking: 44,
  },
  reposters: [{ id: 2, soundcloud_id: 'curator-sc', display_name: 'Trusted Curator', slug: 'curator', avatar_url: null, ranking: 12 }],
  best_reposter_rank: 12,
  reposter_count: 4,
  current_decision: null,
  decided_at: null,
  action_state: { like: null, monthly_playlist: null, error: null },
  keep_probability: null,
  prediction_model_version: null,
  prediction_explanation: null,
  ...overrides,
});

describe('FeedTrackCard', () => {
  it('separates uploader and reposter attribution and shows rank/count', () => {
    render(<FeedTrackCard item={makeItem()} isPlaying={false} onPlay={vi.fn()} onDecide={vi.fn()} />);
    expect(screen.getByText(/Uploaded by/)).toHaveTextContent('Uploaded by Original Artist');
    expect(screen.getByText(/Reposted by/)).toHaveTextContent('Reposted by Trusted Curator +3 other reposters');
    expect(screen.getByText('#12')).toBeInTheDocument();
  });

  it('offers keyboard-accessible play, Nope, neutral hide, and keep actions', () => {
    const onPlay = vi.fn();
    const onDecide = vi.fn();
    const item = makeItem();
    render(<FeedTrackCard item={item} isPlaying={false} onPlay={onPlay} onDecide={onDecide} />);

    fireEvent.click(screen.getByRole('button', { name: 'Play Signal Path' }));
    fireEvent.click(screen.getByRole('button', { name: /Nope/ }));
    fireEvent.click(screen.getByRole('button', { name: /Hide without/ }));
    fireEvent.click(screen.getByRole('button', { name: /Keep/ }));

    expect(onPlay).toHaveBeenCalledWith(item);
    expect(onDecide.mock.calls.map((call) => call[1])).toEqual(['nope', 'hide', 'keep']);
  });

  it('shows a running SoundCloud job as pending sync', () => {
    render(
      <FeedTrackCard
        item={makeItem({
          current_decision: 'keep',
          action_state: { like: 'running', monthly_playlist: 'pending', error: null },
        })}
        isPlaying={false}
        onPlay={vi.fn()}
        onDecide={vi.fn()}
      />
    );
    expect(screen.getByRole('status')).toHaveTextContent('SoundCloud sync pending');
  });

  it('shows failed SoundCloud synchronization while preserving the keep state', () => {
    render(
      <FeedTrackCard
        item={makeItem({
          current_decision: 'keep',
          action_state: { like: 'complete', monthly_playlist: 'error', error: 'retry later' },
        })}
        isPlaying={false}
        onPlay={vi.fn()}
        onDecide={vi.fn()}
      />
    );
    expect(screen.getByRole('status')).toHaveTextContent('SoundCloud sync failed');
    expect(screen.getByRole('button', { name: /Keep/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('links to the SoundCloud track page in a new tab when a permalink exists', () => {
    render(
      <FeedTrackCard
        item={makeItem({ permalink_url: 'https://soundcloud.com/original/signal-path' })}
        isPlaying={false}
        onPlay={vi.fn()}
        onDecide={vi.fn()}
      />
    );
    const link = screen.getByRole('link', { name: 'Open Signal Path on SoundCloud' });
    expect(link).toHaveAttribute('href', 'https://soundcloud.com/original/signal-path');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('omits the SoundCloud link when no permalink is known', () => {
    render(<FeedTrackCard item={makeItem()} isPlaying={false} onPlay={vi.fn()} onDecide={vi.fn()} />);
    expect(screen.queryByRole('link', { name: /on SoundCloud/ })).not.toBeInTheDocument();
  });

  it('shows the predicted keep probability as a percentage badge', () => {
    render(
      <FeedTrackCard
        item={makeItem({ keep_probability: 0.73, prediction_model_version: 'typesafe/jev-latest' })}
        isPlaying={false}
        onPlay={vi.fn()}
        onDecide={vi.fn()}
      />
    );
    const badge = screen.getByText('73%');
    expect(badge).toHaveAttribute('title', 'Predicted keep probability (typesafe/jev-latest)');
  });

  it('renders no score badge when the track is unscored', () => {
    render(<FeedTrackCard item={makeItem()} isPlaying={false} onPlay={vi.fn()} onDecide={vi.fn()} />);
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });
});
