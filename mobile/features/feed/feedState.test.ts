import { describe, expect, it } from 'vitest';
import type { FeedItem } from '@music-minion/shared';
import { optimisticallyDecideFeedItems, parseFeedScreenState } from './feedState';

const item = (): FeedItem => ({
  id: '7',
  soundcloud_id: '7',
  local_track_id: null,
  title: 'Track',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 10_000,
  genre: null,
  event_at: '2026-09-12T00:00:00Z',
  uploaded_at: null,
  released_at: null,
  sources: ['repost'],
  uploader: null,
  reposters: [],
  best_reposter_rank: null,
  reposter_count: 0,
  current_decision: null,
  decided_at: null,
  action_state: { like: null, monthly_playlist: null, error: null },
  keep_probability: null,
  prediction_model_version: null,
  prediction_explanation: null,
});

describe('mobile feed screen behavior', () => {
  it('restores source and rank from route state and rejects invalid values', () => {
    expect(parseFeedScreenState({ source: 'reposts', maxRank: '75', inLibrary: 'true' })).toEqual({
      source: 'reposts',
      maxRank: 75,
      inLibrary: true,
    });
    expect(parseFeedScreenState({ source: 'bad', maxRank: '76' })).toEqual({
      source: 'all',
      maxRank: undefined,
      inLibrary: false,
    });
  });

  it('keeps hearts visible with pending SC state and removes Nope/hide choices', () => {
    const kept = optimisticallyDecideFeedItems([item()], '7', 'keep');
    expect(kept[0].current_decision).toBe('keep');
    expect(kept[0].action_state.like).toBe('pending');
    expect(optimisticallyDecideFeedItems([item()], '7', 'nope')).toEqual([]);
    expect(optimisticallyDecideFeedItems([item()], '7', 'hide')).toEqual([]);
  });
});
