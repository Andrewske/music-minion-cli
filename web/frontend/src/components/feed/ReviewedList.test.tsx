import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReviewedItem } from '../../api/feed';
import { ReviewedRow } from './ReviewedList';
import { describeListen } from './reviewed';

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
