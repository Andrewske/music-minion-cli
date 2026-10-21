import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, type InfiniteData } from '@tanstack/react-query';
import type { ReviewedItem, ReviewedPage } from '../../api/feed';
import { ReviewedRow } from './ReviewedList';
import { REVIEWED_QUERY_KEY, cacheMaterializedReviewed, describeListen, reviewedRateOptions } from './reviewed';
import { INITIAL_LISTEN_STATE } from '../../lib/feedListen';
import { useListenStore } from '../../stores/listenStore';

const makeItem = (overrides: Partial<ReviewedItem> = {}): ReviewedItem => ({
  decision_id: 1,
  soundcloud_id: '42',
  decision: 'not_quite',
  decided_at: '2026-10-01T12:00:00+00:00',
  decided_key: '2026-10-01T12:00:00Z',
  surface: 'web',
  listen_seconds: 42,
  max_position_ms: 90_000,
  local_track_id: 7,
  title: 'Signal Path',
  artist_name: 'Original Artist',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 200_000,
  access: 'playable',
  note: null,
  note_updated_at: null,
  ...overrides,
});

const renderRow = (item: ReviewedItem) => {
  const handlers = { onPlay: vi.fn(), onDecide: vi.fn(), onEditNote: vi.fn() };
  render(<ReviewedRow item={item} isUpdating={false} isPlaying={false} {...handlers} />);
  return handlers;
};

describe('ReviewedRow', () => {
  it('shows verdict, listen time and lets the verdict change inline', () => {
    const handlers = renderRow(makeItem());
    expect(screen.getByText(/Not quite ·/)).toBeInTheDocument();
    expect(screen.getByText('0:42 played · reached 1:30')).toBeInTheDocument();
    const current = screen.getByRole('button', { name: /^Not quite/ });
    expect(current).toHaveAttribute('aria-pressed', 'true');
    expect(current).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /^Keep/ }));
    expect(handlers.onDecide).toHaveBeenCalledWith(expect.objectContaining({ soundcloud_id: '42' }), 'keep');
  });

  it('plays the track and opens the note editor with the existing note', () => {
    const handlers = renderRow(makeItem({ note: 'vocals too much' }));
    fireEvent.click(screen.getByRole('button', { name: 'Play Signal Path' }));
    expect(handlers.onPlay).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Edit note: vocals too much' }));
    expect(handlers.onEditNote).toHaveBeenCalledWith({
      soundcloudId: '42',
      title: 'Signal Path',
      note: 'vocals too much',
    });
  });

  it('labels legacy hide rows and leaves every verdict available', () => {
    renderRow(makeItem({ decision: 'hide', listen_seconds: null, max_position_ms: null }));
    expect(screen.getByText(/Hidden \(legacy\)/)).toBeInTheDocument();
    expect(screen.getByText('Not tracked')).toBeInTheDocument();
    for (const name of [/^Nope/, /^Not quite/, /^Keep/]) {
      expect(screen.getByRole('button', { name })).toBeEnabled();
    }
  });
});

describe('describeListen', () => {
  it('omits the reached position when unknown', () => {
    expect(describeListen({ listen_seconds: 5, max_position_ms: null })).toBe('0:05 played');
  });
});

describe('reviewedRateOptions', () => {
  it('sends listen stats from the global tracker when the track was replayed', () => {
    useListenStore.setState(INITIAL_LISTEN_STATE);
    const { record } = useListenStore.getState();
    record({ kind: 'progress', source: 'A', trackId: 7, positionMs: 0 });
    record({ kind: 'progress', source: 'A', trackId: 7, positionMs: 3_000 });
    expect(reviewedRateOptions(7)).toEqual({ surface: 'web_reviewed', listenSeconds: 3, maxPositionMs: 3_000 });
  });

  it('omits listen stats when not replayed so the backend carries them forward', () => {
    useListenStore.setState(INITIAL_LISTEN_STATE);
    expect(reviewedRateOptions(7)).toEqual({ surface: 'web_reviewed' });
    expect(reviewedRateOptions(null)).toEqual({ surface: 'web_reviewed' });
  });
});

describe('cacheMaterializedReviewed', () => {
  it('lets a re-rate send the tally of a row that had no local track before playback', () => {
    useListenStore.setState(INITIAL_LISTEN_STATE);
    const queryClient = new QueryClient();
    const key = [...REVIEWED_QUERY_KEY, { filter: undefined }];
    const page: ReviewedPage = { items: [makeItem({ local_track_id: null })], next_cursor: null };
    queryClient.setQueryData<InfiniteData<ReviewedPage>>(key, { pages: [page], pageParams: [undefined] });
    // Play materializes track 55, then the player tallies it.
    cacheMaterializedReviewed(queryClient, '42', 55);
    const { record } = useListenStore.getState();
    record({ kind: 'progress', source: 'A', trackId: 55, positionMs: 0 });
    record({ kind: 'progress', source: 'A', trackId: 55, positionMs: 4_000 });
    const row = queryClient.getQueryData<InfiniteData<ReviewedPage>>(key)?.pages[0].items[0];
    expect(row?.local_track_id).toBe(55);
    expect(reviewedRateOptions(row?.local_track_id ?? null)).toEqual({
      surface: 'web_reviewed',
      listenSeconds: 4,
      maxPositionMs: 4_000,
    });
  });
});
