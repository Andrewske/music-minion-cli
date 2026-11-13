import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'react-toastify';
import { getUnfollowSuggestions, keepFollowing, unfollowBatch, unfollowSuggested } from '../../api/unfollowSuggestions';
import type {
  UnfollowAccountResponse, UnfollowBatchResponse, UnfollowCandidate, UnfollowSuggestionsResponse,
} from '../../api/unfollowSuggestions';
import { chunk, withCandidatesBack, withoutCandidates } from '../../hooks/useUnfollowSuggestions';
import { candidateChips } from './format';
import { UnfollowView } from './UnfollowView';

vi.mock('../../api/unfollowSuggestions', () => ({
  getUnfollowSuggestions: vi.fn(),
  keepFollowing: vi.fn(),
  unfollowSuggested: vi.fn(),
  unfollowBatch: vi.fn(),
  UNFOLLOW_BATCH_SIZE: 2,
}));
vi.mock('react-toastify', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

function makeCandidate(id: number, overrides: Partial<UnfollowCandidate> = {}): UnfollowCandidate {
  return {
    discovery_artist_id: id, soundcloud_user_id: String(1000 + id), display_name: `Artist ${id}`,
    slug: `artist-${id}`, avatar_url: null, followers: null, tier: null, followed_at: null,
    items: 2888, reposts: 2800, uploads: 88, good: 117, unique_finds: 2, liked_uploads: 0,
    value: 0.6, noise_per_month: 412.4, last_find_at: null, last_item_at: null, ...overrides,
  };
}

function makeResponse(redundant: UnfollowCandidate[], count = 1945): UnfollowSuggestionsResponse {
  return {
    sections: { redundant, dormant: [makeCandidate(90, { items: 0 })], labels: [], low_yield: [] },
    following: { count, limit: 2000 },
    generated_at: '2026-11-12T00:00:00Z',
  };
}

const batchOk = (ids: number[]): UnfollowBatchResponse => ({
  results: ids.map((id) => ({ id, ok: true })), stopped: false, error: null,
});

function renderView(): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><UnfollowView /></QueryClientProvider>);
  return client;
}

const row = (id: number): HTMLElement => screen.getByTestId(`account-row-${id}`);
const meter = (): string => screen.getByTestId('following-meter').textContent ?? '';

describe('UnfollowView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getUnfollowSuggestions).mockResolvedValue(
      makeResponse([makeCandidate(1, { tier: 'B' }), makeCandidate(2), makeCandidate(3)]),
    );
  });

  it('shows section tabs with counts, the meter, chips and the tier chip', async () => {
    renderView();
    await screen.findByText('Artist 1');
    expect(screen.getByRole('tab', { name: /Redundant reposters 3/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /Dormant 1/ })).toBeInTheDocument();
    expect(meter()).toContain('Following 1,945 / 2,000 on SoundCloud · 55 left');
    expect(within(row(1)).getByText('2,888 in feed')).toBeInTheDocument();
    expect(within(row(1)).getByText('2 only from them')).toBeInTheDocument();
    expect(within(row(1)).getByText('B')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /Dormant/ }));
    expect(within(row(90)).getByText('nothing in the feed')).toBeInTheDocument();
  });

  it('unfollows one row at once and drops the meter; rolls back on failure', async () => {
    let reject: (e: Error) => void = () => undefined;
    vi.mocked(unfollowSuggested).mockReturnValue(new Promise<UnfollowAccountResponse>((_r, rj) => { reject = rj; }));
    renderView();
    await screen.findByText('Artist 1');
    fireEvent.click(within(row(2)).getByRole('button', { name: 'Unfollow' }));
    await waitFor(() => expect(screen.queryByText('Artist 2')).toBeNull());
    expect(meter()).toContain('1,944 / 2,000');
    await act(async () => reject(new Error('SoundCloud returned 502, try again')));
    await screen.findByText('Artist 2');
    expect(meter()).toContain('1,945 / 2,000');
    expect(toast.error).toHaveBeenCalledWith('SoundCloud returned 502, try again');
  });

  it('keep removes the row without touching the meter', async () => {
    vi.mocked(keepFollowing).mockResolvedValue({ ok: true });
    const client = renderView();
    await screen.findByText('Artist 1');
    client.setQueryDefaults(['unfollow-suggestions'], { staleTime: Infinity });
    vi.mocked(getUnfollowSuggestions).mockResolvedValue(makeResponse([makeCandidate(1), makeCandidate(3)]));
    fireEvent.click(within(row(2)).getByRole('button', { name: 'Keep' }));
    await waitFor(() => expect(screen.queryByText('Artist 2')).toBeNull());
    expect(vi.mocked(keepFollowing).mock.calls[0]?.[0]).toBe(2);
    expect(meter()).toContain('1,945 / 2,000');
  });

  it('bulk unfollows a section in batches after confirming', async () => {
    vi.mocked(unfollowBatch).mockImplementation(async (ids) => batchOk(ids));
    renderView();
    await screen.findByText('Artist 1');
    vi.mocked(getUnfollowSuggestions).mockResolvedValue(makeResponse([], 1942));
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow all 3' }));
    expect(screen.getByText('Unfollow 3 accounts?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow 3' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Unfollowed 3'));
    expect(vi.mocked(unfollowBatch).mock.calls).toEqual([[[1, 2]], [[3]]]);
    expect(screen.queryByText('Artist 1')).toBeNull();
    await waitFor(() => expect(meter()).toContain('1,942 / 2,000'));
  });

  it('stops a bulk run when SoundCloud fails service-wide', async () => {
    vi.mocked(unfollowBatch).mockResolvedValue({
      results: [{ id: 1, ok: true }, { id: 2, ok: false, status: 503, error: 'Could not reach SoundCloud' }],
      stopped: true,
      error: 'Could not reach SoundCloud',
    });
    renderView();
    await screen.findByText('Artist 1');
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow all 3' }));
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow 3' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Stopped after 1 unfollows: Could not reach SoundCloud'));
    expect(unfollowBatch).toHaveBeenCalledTimes(1);
  });

  it('Stop finishes the batch in flight and sends no more', async () => {
    let release: () => void = () => undefined;
    vi.mocked(unfollowBatch).mockImplementation((ids) => new Promise((r) => { release = () => r(batchOk(ids)); }));
    renderView();
    await screen.findByText('Artist 1');
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow all 3' }));
    fireEvent.click(screen.getByRole('button', { name: 'Unfollow 3' }));
    const progress = await screen.findByTestId('bulk-progress');
    expect(within(row(1)).getByRole('button', { name: 'Unfollow' })).toBeDisabled();
    fireEvent.click(within(progress).getByRole('button', { name: 'Stop' }));
    await act(async () => release());
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Unfollowed 2'));
    expect(unfollowBatch).toHaveBeenCalledTimes(1);
  });
});

describe('unfollow cache transforms', () => {
  const data = makeResponse([makeCandidate(1), makeCandidate(2)]);

  it('removes rows and lowers the count by the unfollowed number only', () => {
    const out = withoutCandidates(data, new Set([1, 90]), 1);
    expect(out.sections.redundant.map((c) => c.discovery_artist_id)).toEqual([2]);
    expect(out.sections.dormant).toEqual([]);
    expect(out.following.count).toBe(1944);
  });

  it('puts rows back at their old position', () => {
    const out = withoutCandidates(data, new Set([1]), 1);
    const back = withCandidatesBack(out, [{ list: 'redundant', index: 0, item: makeCandidate(1) }], 1);
    expect(back.sections.redundant.map((c) => c.discovery_artist_id)).toEqual([1, 2]);
    expect(back.following.count).toBe(1945);
  });

  it('chunks ids into batches', () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunk([], 25)).toEqual([]);
  });

  it('chips skip liked uploads when zero and show last find age', () => {
    const now = Date.parse('2026-11-12T00:00:00Z');
    const c = makeCandidate(1, { last_find_at: '2026-06-01T00:00:00+00:00', liked_uploads: 0 });
    expect(candidateChips(c, now)).toEqual([
      '2,888 in feed', '412/mo', '117 liked/kept', '2 only from them', 'last find 5 mo ago',
    ]);
  });
});
