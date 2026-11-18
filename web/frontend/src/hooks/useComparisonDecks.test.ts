import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComparisonPair, TrackInfo } from '../types';

const player = vi.hoisted(() => ({
  state: { currentTrack: null as { id: number } | null, isPlaying: false, pause: vi.fn(), resume: vi.fn() },
  playFromPosition: vi.fn(),
}));

vi.mock('../stores/playerStore', () => ({
  usePlayerStore: { getState: () => player.state },
  getCurrentPosition: () => 42_000,
  playFromPosition: player.playFromPosition,
}));

const { toggleDeck, otherDeck } = await import('./useComparisonDecks');

const track = (id: number): TrackInfo => ({
  id, title: `T${id}`, rating: 1500, comparison_count: 0, wins: 0, losses: 0, has_waveform: false,
});
const pair: ComparisonPair = { track_a: track(1), track_b: track(2) };
const context = { type: 'comparison', track_ids: [1, 2], shuffle: false };

describe('toggleDeck', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    player.state.currentTrack = null;
    player.state.isPlaying = false;
  });

  it('starts the other deck at the playing position', () => {
    player.state.currentTrack = { id: 1 };
    toggleDeck(pair, pair.track_b);
    expect(player.playFromPosition).toHaveBeenCalledWith(pair.track_b, context, 42_000);
  });

  it('starts from zero when nothing in the pair is playing', () => {
    player.state.currentTrack = { id: 99 };
    toggleDeck(pair, pair.track_a);
    expect(player.playFromPosition).toHaveBeenCalledWith(pair.track_a, context, 0);
  });

  it('pauses and resumes the deck that is already current', () => {
    player.state.currentTrack = { id: 2 };
    player.state.isPlaying = true;
    toggleDeck(pair, pair.track_b);
    expect(player.state.pause).toHaveBeenCalled();
    player.state.isPlaying = false;
    toggleDeck(pair, pair.track_b);
    expect(player.state.resume).toHaveBeenCalled();
    expect(player.playFromPosition).not.toHaveBeenCalled();
  });
});

describe('otherDeck', () => {
  it('flips A to B, and defaults to A', () => {
    player.state.currentTrack = { id: 1 };
    expect(otherDeck(pair).id).toBe(2);
    player.state.currentTrack = { id: 2 };
    expect(otherDeck(pair).id).toBe(1);
    player.state.currentTrack = null;
    expect(otherDeck(pair).id).toBe(1);
  });
});
