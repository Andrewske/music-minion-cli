import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DndContext } from '@dnd-kit/core';
import { describe, expect, it, vi } from 'vitest';
import type { Bucket } from '../../api/buckets';
import type { PlaylistTrackEntry } from '../../types';
import { BucketComponent } from './Bucket';

const bucket: Bucket = {
  id: 'b1', name: 'Openers', emoji_id: null, position: 0, track_ids: [11, 12],
  linked_playlist_id: null, linked_playlist_name: null, linked_playlist_soundcloud_id: null,
};

const track = (id: number, title: string): PlaylistTrackEntry => ({
  id, title, artist: 'Artist', bpm: 140.4, key_signature: '8A', rating: 1512,
  wins: 0, losses: 0, comparison_count: 0,
});

function renderBucket(onTrackClick: (id: number) => void): void {
  const noop = vi.fn().mockResolvedValue(undefined);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DndContext>
        <BucketComponent
          bucket={bucket}
          tracks={[track(11, 'First Light'), track(12, 'Second Wind')]}
          bucketIndex={0}
          totalBuckets={1}
          currentTrackId={12}
          onMove={noop}
          onShuffle={noop}
          onDelete={noop}
          onUpdate={noop}
          onTrackClick={onTrackClick}
        />
      </DndContext>
    </QueryClientProvider>,
  );
  // Buckets start collapsed; the first button in the header is the chevron.
  fireEvent.click(screen.getAllByRole('button')[0]);
}

describe('BucketComponent track rows', () => {
  it('plays a bucket track when its row is clicked', () => {
    const onTrackClick = vi.fn();
    renderBucket(onTrackClick);
    fireEvent.click(screen.getByLabelText(/First Light: click to play/));
    expect(onTrackClick).toHaveBeenCalledWith(11);
  });

  it('plays on Enter so keyboard users are not forced into a drag', () => {
    const onTrackClick = vi.fn();
    renderBucket(onTrackClick);
    fireEvent.keyDown(screen.getByLabelText(/Second Wind: click to play/), { key: 'Enter', code: 'Enter' });
    expect(onTrackClick).toHaveBeenCalledWith(12);
  });

  it('renders the same columns as the unassigned list', () => {
    renderBucket(vi.fn());
    const row = screen.getByLabelText(/Second Wind: click to play/);
    expect(row.textContent).toContain('140');
    expect(row.textContent).toContain('8A');
    expect(row.textContent).toContain('1512');
  });
});
