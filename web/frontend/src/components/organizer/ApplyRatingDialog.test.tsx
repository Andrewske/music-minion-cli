import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlaylistTrackEntry } from '../../types';
import * as bucketsApi from '../../api/buckets';
import { ApplyRatingDialog } from './ApplyRatingDialog';
import { methodLabel } from './ratingMethodLabel';

vi.mock('../../api/buckets', async (importOriginal) => ({
  isNoopRating: (await importOriginal<typeof import('../../api/buckets')>()).isNoopRating,
  previewBucketRating: vi.fn(),
  applyBucketRating: vi.fn(),
  undoBucketRating: vi.fn(),
}));
vi.mock('react-toastify', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const track = (id: number, title: string): PlaylistTrackEntry => ({
  id, title, artist: 'Artist', rating: 1500, wins: 0, losses: 0, comparison_count: 0,
});

const preview = {
  track_ids: [11, 12],
  method: 'redistribute' as const,
  rows: [
    { track_id: 11, before: 1450, after: 1550 },
    { track_id: 12, before: 1550, after: 1450 },
  ],
};

function renderDialog(onClose = vi.fn(), isReordering = false): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ApplyRatingDialog
        open
        onClose={onClose}
        bucketId="b1"
        bucketName="Openers"
        playlistId={7}
        tracks={[track(11, 'First Light'), track(12, 'Second Wind')]}
        isReordering={isReordering}
      />
    </QueryClientProvider>,
  );
}

describe('ApplyRatingDialog', () => {
  beforeEach(() => {
    vi.mocked(bucketsApi.previewBucketRating).mockResolvedValue(preview);
    vi.mocked(bucketsApi.applyBucketRating).mockReset();
  });

  it('shows before/after per track and applies the previewed order', async () => {
    vi.mocked(bucketsApi.applyBucketRating).mockResolvedValue({ ...preview, application_id: 'a1' });
    const onClose = vi.fn();
    renderDialog(onClose);

    expect(await screen.findByText('Artist - First Light')).toBeTruthy();
    expect(screen.getByText('1450 → 1550')).toBeTruthy();
    expect(screen.getByText('+100')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Apply rating' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(bucketsApi.applyBucketRating).toHaveBeenCalledWith('b1', [11, 12]);
  });

  it('stays open and refetches the preview on a 409', async () => {
    vi.mocked(bucketsApi.applyBucketRating).mockRejectedValue(
      Object.assign(new Error('order changed'), { status: 409 }),
    );
    const onClose = vi.fn();
    renderDialog(onClose);
    await screen.findByText('Artist - First Light');

    fireEvent.click(screen.getByRole('button', { name: 'Apply rating' }));
    await waitFor(() => expect(bucketsApi.previewBucketRating).toHaveBeenCalledTimes(2));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('disables apply when the order already matches the ratings', async () => {
    vi.mocked(bucketsApi.previewBucketRating).mockResolvedValue({
      ...preview,
      rows: [{ track_id: 11, before: 1550, after: 1550 }, { track_id: 12, before: 1450, after: 1450 }],
    });
    renderDialog();
    expect(await screen.findByText('Ratings already match this order')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Apply rating' }).hasAttribute('disabled')).toBe(true);
  });

  it('blocks apply while a reorder is still saving', async () => {
    renderDialog(vi.fn(), true);
    await screen.findByText('Artist - First Light');
    expect(screen.getByRole('button', { name: 'Apply rating' }).hasAttribute('disabled')).toBe(true);
  });
});

describe('methodLabel', () => {
  it('reports the real band endpoints for an unrated bucket', () => {
    const band = {
      ...preview,
      method: 'band' as const,
      rows: [{ track_id: 1, before: 1700, after: 1800 }, { track_id: 2, before: 1700, after: 1600 }],
    };
    expect(methodLabel(band)).toBe('Unrated bucket: spread 1800 to 1600.');
  });
});
