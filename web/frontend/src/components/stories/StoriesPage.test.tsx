import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import type { StoriesResponse } from '../../api/stories';
import { getStories, markStoryListened } from '../../api/stories';
import { materializeFeedItems, rateFeedItem } from '../../api/feed';
import { INITIAL_LISTEN_STATE } from '../../lib/feedListen';
import { useListenStore } from '../../stores/listenStore';
import { usePlayerStore } from '../../stores/playerStore';
import { useStoriesStore } from '../../stores/storiesStore';
import { makeArtist, makeResponse, makeTrack } from './storiesFixtures';
import { StoriesPage } from './StoriesPage';

vi.mock('../../api/stories', () => ({
  getStories: vi.fn(),
  markStoryListened: vi.fn(async (id: string) => ({ soundcloud_id: id, listened: true })),
}));
vi.mock('../../api/feed', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/feed')>()),
  rateFeedItem: vi.fn(async (id: string, decision: string) => ({
    soundcloud_id: id,
    current_decision: decision,
    decided_at: '2026-11-08T20:00:00Z',
    local_track_id: null,
    action_state: { like: null, monthly_playlist: null, error: null },
  })),
  materializeFeedItems: vi.fn(async (ids: string[]) => ids.map((id) => ({ soundcloud_id: id, local_track_id: 900 }))),
}));
vi.mock('../../stores/playerStore', async () => {
  const { create } = await import('zustand');
  interface FakePlayer {
    currentTrack: { id: number } | null;
    isPlaying: boolean;
    play: Mock;
    pause: Mock;
    resume: Mock;
  }
  const usePlayerStore = create<FakePlayer>(() => ({
    currentTrack: null,
    isPlaying: false,
    play: vi.fn(async () => undefined),
    pause: vi.fn(async () => undefined),
    resume: vi.fn(async () => undefined),
  }));
  return { usePlayerStore, getCurrentPosition: () => 0 };
});
vi.mock('../feed/FeedWaveform', () => ({ FeedWaveform: () => <div data-testid="waveform" /> }));
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }) }));

const RESPONSE: StoriesResponse = makeResponse([
  makeArtist(1, [
    makeTrack('a1', { local_track_id: 101, title: 'Na ostri noze', artist_name: '3Nightz' }),
    makeTrack('a2', { local_track_id: 102, listened: true, decision: 'nope' }),
    makeTrack('a3', { local_track_id: 103 }),
  ], { display_name: 'MIRR.IMG' }),
  makeArtist(2, [makeTrack('b1')], { display_name: 'Subsidia' }),
]);

const playMock = (): Mock => usePlayerStore.getState().play;
const playedIds = (): number[] => playMock().mock.calls.map(([track]) => track.id);
const artistNav = (): HTMLElement => screen.getAllByRole('navigation', { name: 'Followed artists' })[0];

function renderPage(response: StoriesResponse = RESPONSE): void {
  (getStories as Mock).mockResolvedValue(response);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <StoriesPage />
    </QueryClientProvider>
  );
}

/** What the global player looks like after this page started track `id`. */
function playerLoaded(id: number): void {
  act(() => usePlayerStore.setState({ currentTrack: { id }, isPlaying: true }));
}

beforeEach(() => {
  vi.clearAllMocks();
  useStoriesStore.getState().reset();
  useListenStore.setState(INITIAL_LISTEN_STATE);
  usePlayerStore.setState({ currentTrack: null, isPlaying: false });
});

describe('StoriesPage', () => {
  it('selects the first artist without autoplaying', async () => {
    renderPage();
    expect(await screen.findByText(/reposted a track/)).toBeInTheDocument();
    expect(within(artistNav()).getByRole('button', { name: 'MIRR.IMG, 2 unheard' })).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', { name: 'Play Na ostri noze' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Track a2 \(heard\)/ })).toHaveAttribute('data-listened', 'true');
    expect(playMock()).not.toHaveBeenCalled();
  });

  it('plays from the artwork as a one-track queue', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Play Na ostri noze' }));
    await waitFor(() => expect(playMock()).toHaveBeenCalledTimes(1));
    expect(playMock()).toHaveBeenCalledWith(
      expect.objectContaining({ id: 101, title: 'Na ostri noze', artist: '3Nightz' }),
      { type: 'feed', track_ids: [101], shuffle: false }
    );
  });

  it('Skip rates nope with the stories surface and plays the next unheard track', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /^Skip/ }));
    await waitFor(() => expect(playedIds()).toEqual([103]));
    expect(rateFeedItem).toHaveBeenCalledWith('a1', 'nope', expect.objectContaining({ surface: 'stories', listenSeconds: 0 }));
    expect(within(screen.getByRole('list', { name: 'Artist tracks' })).getAllByText('Skipped')).toHaveLength(2);
  });

  it('Like rates keep and does not advance', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /^Like/ }));
    await waitFor(() => expect(rateFeedItem).toHaveBeenCalledWith('a1', 'keep', expect.objectContaining({ surface: 'stories' })));
    expect(playMock()).not.toHaveBeenCalled();
    expect(screen.getByText('Liked')).toBeInTheDocument();
  });

  it('advances on natural track end and drops the finished artist when moving on', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Track a3' }));
    await waitFor(() => expect(playedIds()).toEqual([103]));
    playerLoaded(103);
    act(() => usePlayerStore.setState({ currentTrack: null, isPlaying: false }));
    await waitFor(() => expect(playedIds()).toEqual([103, 101]));
    // Ended with no real playback (stream error / player-bar Next): advance, but don't persist a listen.
    expect(markStoryListened).not.toHaveBeenCalled();

    playerLoaded(101);
    act(() => usePlayerStore.setState({ currentTrack: null, isPlaying: false }));
    // b1 has no local id yet: materialized before playing.
    await waitFor(() => expect(playedIds()).toEqual([103, 101, 900]));
    expect(materializeFeedItems).toHaveBeenCalledWith(['b1']);
    expect(within(artistNav()).queryByRole('button', { name: /MIRR.IMG/ })).not.toBeInTheDocument();
    expect(within(artistNav()).getByRole('button', { name: /Subsidia/ })).toHaveAttribute('aria-current', 'true');
  });

  it('Previous returns to the earlier artist and re-shows it', async () => {
    renderPage(makeResponse([RESPONSE.artists[0], makeArtist(2, [makeTrack('b1', { local_track_id: 201 })], { display_name: 'Subsidia' })]));
    fireEvent.click(await screen.findByRole('button', { name: 'Track a3' }));
    await waitFor(() => expect(playedIds()).toEqual([103]));
    fireEvent.click(screen.getByRole('button', { name: /^Not quite/ }));
    await waitFor(() => expect(playedIds()).toEqual([103, 101]));
    fireEvent.click(screen.getByRole('button', { name: /^Skip/ }));
    await waitFor(() => expect(playedIds()).toEqual([103, 101, 201]));
    expect(within(artistNav()).queryByRole('button', { name: /MIRR.IMG/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Previous track' }));
    await waitFor(() => expect(playedIds()).toEqual([103, 101, 201, 101]));
    expect(within(artistNav()).getByRole('button', { name: /MIRR.IMG/ })).toHaveAttribute('aria-current', 'true');
  });

  it('marks the current track listened once after 5 seconds of playback', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Play Na ostri noze' }));
    await waitFor(() => expect(playedIds()).toEqual([101]));
    act(() => useListenStore.setState({ tallies: { 101: { listenedMs: 4_000, maxPositionMs: 4_000 } } }));
    expect(markStoryListened).not.toHaveBeenCalled();
    act(() => useListenStore.setState({ tallies: { 101: { listenedMs: 6_000, maxPositionMs: 6_000 } } }));
    act(() => useListenStore.setState({ tallies: { 101: { listenedMs: 9_000, maxPositionMs: 9_000 } } }));
    await waitFor(() => expect(markStoryListened).toHaveBeenCalledTimes(1));
    expect(markStoryListened).toHaveBeenCalledWith('a1');
    expect(within(artistNav()).getByRole('button', { name: 'MIRR.IMG, 1 unheard' })).toBeInTheDocument();
  });

  it('pauses instead of restarting when the artwork is clicked while playing', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Play Na ostri noze' }));
    await waitFor(() => expect(playedIds()).toEqual([101]));
    playerLoaded(101);
    fireEvent.click(screen.getByRole('button', { name: 'Pause Na ostri noze' }));
    expect(usePlayerStore.getState().pause).toHaveBeenCalled();
    expect(playMock()).toHaveBeenCalledTimes(1);
  });

  it('Reload mid-track adopts the playing story without restarting it', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Play Na ostri noze' }));
    await waitFor(() => expect(playedIds()).toEqual([101]));
    playerLoaded(101);
    fireEvent.click(screen.getByRole('button', { name: 'Reload stories' }));
    await waitFor(() => expect(getStories).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reload stories' })).not.toBeDisabled());
    expect(playMock()).toHaveBeenCalledTimes(1);
    expect(useStoriesStore.getState().session?.current).toEqual({ artistId: 1, soundcloudId: 'a1' });
  });

  it('Skip on the last unheard story pauses it instead of playing on under caught-up', async () => {
    renderPage(makeResponse([makeArtist(1, [makeTrack('a1', { local_track_id: 101 })])]));
    fireEvent.click(await screen.findByRole('button', { name: 'Play Track a1' }));
    await waitFor(() => expect(playedIds()).toEqual([101]));
    playerLoaded(101);
    fireEvent.click(screen.getByRole('button', { name: /^Skip/ }));
    expect(await screen.findByText("You're all caught up")).toBeInTheDocument();
    expect(usePlayerStore.getState().pause).toHaveBeenCalledTimes(1);
  });

  it('shows the caught-up state when nothing is unheard', async () => {
    renderPage(makeResponse([]));
    expect(await screen.findByText("You're all caught up")).toBeInTheDocument();
  });
});
