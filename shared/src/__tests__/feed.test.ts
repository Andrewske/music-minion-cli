import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import {
  FEED_PAGE_SIZE,
  applyFeedDecision,
  feedRatingToDecision,
  getFeed,
  getFeedItemBestRank,
  hasPendingFeedSync,
  isFeedSyncFailed,
  isFeedSyncPending,
  materializeFeedItem,
  mergeFeedDecisionResponse,
  normalizeFeedItem,
  rateFeedItem,
  type FeedItem,
} from '../api/feed';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const item = (overrides: Partial<FeedItem> = {}): FeedItem => ({
  id: '123',
  soundcloud_id: '123',
  local_track_id: null,
  title: 'Track',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 60_000,
  genre: null,
  event_at: '2026-09-12T00:00:00Z',
  uploaded_at: '2026-09-11T00:00:00Z',
  released_at: '2026-09-11T00:00:00Z',
  sources: ['release', 'repost'],
  uploader: {
    id: 1,
    soundcloud_id: 'uploader-sc',
    display_name: 'Uploader',
    slug: 'uploader',
    avatar_url: null,
    ranking: 50,
  },
  reposters: [{ id: 2, soundcloud_id: 'reposter-sc', display_name: 'Reposter', slug: 'reposter', avatar_url: null, ranking: 20 }],
  best_reposter_rank: 20,
  reposter_count: 3,
  current_decision: null,
  decided_at: null,
  action_state: { like: null, monthly_playlist: null, error: null },
  keep_probability: null,
  prediction_model_version: null,
  prediction_explanation: null,
  ...overrides,
});

describe('feed API', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], next_cursor: null }) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('requests 100 chronological items by default', async () => {
    await getFeed();
    expect(FEED_PAGE_SIZE).toBe(100);
    expect(fetchMock).toHaveBeenCalledWith('/api/feed?limit=100', expect.any(Object));
  });

  it('serializes unified source, rank, cursor, and visibility filters', async () => {
    await getFeed({
      source: 'reposts',
      maxRank: 75,
      cursor: 'opaque cursor',
      inLibrary: true,
      showHidden: true,
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/feed?cursor=opaque+cursor&limit=100&source=reposts&max_rank=75&in_library=true&show_hidden=true'
    );
  });

  it('serializes score sort and minimum keep probability', async () => {
    await getFeed({ sort: 'score', minScore: 0.7 });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed?limit=100&sort=score&min_score=0.7');
  });

  it('omits the default event_at sort from the query string', async () => {
    await getFeed({ sort: 'event_at' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed?limit=100');
  });

  it('normalizes release-only items during a rolling deployment', () => {
    const legacy = {
      id: 8,
      soundcloud_id: '8',
      local_track_id: 3,
      title: 'Legacy upload',
      artwork_url: null,
      permalink_url: null,
      duration_ms: 1_000,
      uploaded_at: '2026-09-01T00:00:00Z',
      status: 'liked',
      artist: {
        id: 4,
        display_name: 'Uploader',
        slug: 'uploader',
        avatar_url: null,
        in_top_200: true,
        in_library: false,
      },
    } as unknown as FeedItem;
    expect(normalizeFeedItem(legacy)).toMatchObject({
      sources: ['release'],
      current_decision: 'keep',
      event_at: '2026-09-01T00:00:00Z',
      reposters: [],
      uploader: { ranking: null, soundcloud_id: null },
    });
  });

  it('uses the SoundCloud id and canonical decision for actions', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await rateFeedItem('12/34', 1, { surface: 'mobile', modelVersion: 'v1' });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/feed/12%2F34/rate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ decision: 'keep', surface: 'mobile', model_version: 'v1' }),
      })
    );
    expect(feedRatingToDecision(-1)).toBe('nope');
    expect(feedRatingToDecision(0)).toBe('hide');
  });

  it('materializes streaming-only reposts by SoundCloud id', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({ local_track_id: 9 }) });
    await materializeFeedItem('456');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/feed/456/materialize',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('feed decisions', () => {
  it('keeps the card locally and exposes pending SoundCloud actions', () => {
    const updated = applyFeedDecision(item(), 'keep');
    expect(updated.current_decision).toBe('keep');
    expect(updated.action_state).toEqual({ like: 'pending', monthly_playlist: 'pending', error: null });
  });

  it('retains a local keep when the remote action reports an error', () => {
    const updated = mergeFeedDecisionResponse(item(), {
      soundcloud_id: '123',
      current_decision: 'keep',
      decided_at: '2026-09-13T00:00:00Z',
      local_track_id: 9,
      action_state: { like: 'complete', monthly_playlist: 'error', error: 'playlist unavailable' },
    });
    expect(updated.current_decision).toBe('keep');
    expect(updated.local_track_id).toBe(9);
    expect(updated.action_state.monthly_playlist).toBe('error');
  });

  it('treats claimed (running) jobs as pending and errors as failed', () => {
    expect(isFeedSyncPending({ like: 'complete', monthly_playlist: 'running', error: null })).toBe(true);
    expect(isFeedSyncPending({ like: 'pending', monthly_playlist: null, error: null })).toBe(true);
    expect(isFeedSyncPending({ like: 'complete', monthly_playlist: 'complete', error: null })).toBe(false);
    expect(isFeedSyncPending(undefined)).toBe(false);
    expect(isFeedSyncFailed({ like: 'complete', monthly_playlist: 'error', error: 'boom' })).toBe(true);
    expect(isFeedSyncFailed({ like: 'running', monthly_playlist: null, error: null })).toBe(false);
  });

  it('detects in-flight sync anywhere in the loaded pages', () => {
    const settled = item({ action_state: { like: 'complete', monthly_playlist: 'complete', error: null } });
    const running = item({ action_state: { like: 'running', monthly_playlist: 'pending', error: null } });
    expect(hasPendingFeedSync([{ items: [settled] }, { items: [running] }])).toBe(true);
    expect(hasPendingFeedSync([{ items: [settled] }])).toBe(false);
    expect(hasPendingFeedSync(undefined)).toBe(false);
  });

  it('uses the best qualifying uploader or reposter rank', () => {
    expect(getFeedItemBestRank(item())).toBe(20);
    expect(
      getFeedItemBestRank(
        item({
          sources: ['repost'],
          uploader: { ...item().uploader!, ranking: 1 },
        })
      )
    ).toBe(20);
  });
});
