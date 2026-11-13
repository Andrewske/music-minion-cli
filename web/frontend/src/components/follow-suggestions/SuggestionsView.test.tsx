import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'react-toastify';
import {
  dismissSuggestion, followAccount, getFollowConnections, getFollowSuggestions, getUntieredFollows,
  linkSuggestion, setSuggestionLabel,
} from '../../api/followSuggestions';
import type { FollowAccountResponse } from '../../api/followSuggestions';
import { updateArtist } from '../../api/artists';
import { UNTIERED_KEY } from '../../hooks/useFollowSuggestions';
import {
  EMPTY_UNTIERED, makeConnection, makeConnections, makeResponse, makeSuggestion, makeUntiered,
} from './followSuggestionsFixtures';
import { SuggestionsView } from './SuggestionsView';

vi.mock('../../api/followSuggestions', () => ({
  getFollowSuggestions: vi.fn(),
  getFollowConnections: vi.fn(),
  getUntieredFollows: vi.fn(),
  followAccount: vi.fn(),
  dismissSuggestion: vi.fn(),
  setSuggestionLabel: vi.fn(),
  linkSuggestion: vi.fn(),
}));
vi.mock('../../api/artists', () => ({ updateArtist: vi.fn() }));
vi.mock('react-toastify', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, className }: { children: ReactNode; className?: string }) => <a className={className}>{children}</a>,
}));

const resolved = makeSuggestion();
const unresolved = makeSuggestion({ key: 'name:ghostname', soundcloud_user_id: null, display_name: 'Ghost Name', permalink: null });
const label = makeSuggestion({ key: '200', soundcloud_user_id: '200', display_name: 'Big Label', is_label: true });

function renderView(): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><SuggestionsView /></QueryClientProvider>);
  return client;
}

const row = (key: string): HTMLElement => screen.getByTestId(`account-row-${key}`);

/** What the server returns from now on: mutations settle with a refetch. */
const serverReturns = (data: ReturnType<typeof makeResponse>): void => {
  vi.mocked(getFollowSuggestions).mockResolvedValue(data);
};

describe('SuggestionsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getFollowSuggestions).mockResolvedValue(makeResponse([resolved, unresolved], [label]));
    vi.mocked(getFollowConnections).mockResolvedValue(makeConnections());
    vi.mocked(getUntieredFollows).mockResolvedValue(EMPTY_UNTIERED);
  });

  it('shows Follow for resolved accounts and a search link for unresolved names', async () => {
    renderView();
    await screen.findByText('Wooli');
    expect(within(row('100')).getByRole('button', { name: 'Follow' })).toBeInTheDocument();
    expect(within(row('100')).getByRole('link', { name: 'Wooli' })).toHaveAttribute('href', 'https://soundcloud.com/woolimusic');
    expect(within(row('name:ghostname')).queryByRole('button', { name: 'Follow' })).toBeNull();
    expect(within(row('name:ghostname')).getByRole('link', { name: /Search on SoundCloud/ }))
      .toHaveAttribute('href', 'https://soundcloud.com/search/people?q=Ghost%20Name');
  });

  it('expands the tracks behind the score', async () => {
    renderView();
    await screen.findByText('Wooli');
    expect(screen.queryByText(/Wobble/)).toBeNull();
    fireEvent.click(within(row('100')).getByRole('button', { name: /2 tracks/ }));
    expect(screen.getByText(/Wobble/)).toBeInTheDocument();
    expect(within(row('100')).getByText('remix')).toBeInTheDocument();
  });

  it('removes a followed row at once, disables other Follow buttons, and refreshes untiered', async () => {
    let resolve: (v: FollowAccountResponse) => void = () => undefined;
    vi.mocked(followAccount).mockReturnValue(new Promise((r) => { resolve = r; }));
    vi.mocked(getFollowSuggestions).mockResolvedValue(makeResponse([resolved, makeSuggestion({ key: '101', soundcloud_user_id: '101', display_name: 'Second' })]));
    const client = renderView();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    await screen.findByText('Wooli');

    fireEvent.click(within(row('100')).getByRole('button', { name: 'Follow' }));
    await waitFor(() => expect(screen.queryByTestId('account-row-100')).toBeNull());
    expect(vi.mocked(followAccount).mock.calls[0][0]).toBe('100');
    expect(within(row('101')).getByRole('button', { name: 'Follow' })).toBeDisabled();

    await act(async () => resolve({ ok: true, discovery_artist_id: 9 }));
    await waitFor(() => expect(within(row('101')).getByRole('button', { name: 'Follow' })).toBeEnabled());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: UNTIERED_KEY });
  });

  it('puts the row back and shows an error when follow fails', async () => {
    vi.mocked(followAccount).mockRejectedValue(new Error('SoundCloud said no'));
    renderView();
    await screen.findByText('Wooli');
    fireEvent.click(within(row('100')).getByRole('button', { name: 'Follow' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('SoundCloud said no'));
    expect(row('100')).toBeInTheDocument();
  });

  it('dismisses permanently with an optimistic removal', async () => {
    vi.mocked(dismissSuggestion).mockImplementation(async () => {
      serverReturns(makeResponse([resolved], [label]));
      return { ok: true };
    });
    renderView();
    await screen.findByText('Ghost Name');
    fireEvent.click(within(row('name:ghostname')).getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(screen.queryByText('Ghost Name')).toBeNull());
    expect(vi.mocked(dismissSuggestion).mock.calls[0][0]).toBe('name:ghostname');
  });

  it('shows the SoundCloud following count, and blocks follows at the limit', async () => {
    vi.mocked(getFollowSuggestions).mockResolvedValue(makeResponse([resolved], [], { count: 2000, limit: 2000 }));
    renderView();
    await screen.findByText('Wooli');
    expect(screen.getByTestId('following-meter')).toHaveTextContent('Following 2,000 / 2,000 on SoundCloud · at the limit');
    expect(within(row('100')).getByRole('button', { name: 'Follow' })).toBeDisabled();
  });

  it('links an unresolved name to a pasted SoundCloud profile', async () => {
    vi.mocked(linkSuggestion).mockRejectedValueOnce(new Error('Not a SoundCloud profile link'));
    renderView();
    await screen.findByText('Ghost Name');
    fireEvent.click(within(row('name:ghostname')).getByRole('button', { name: 'Link SoundCloud profile' }));
    const input = within(row('name:ghostname')).getByRole('textbox', { name: 'SoundCloud link for Ghost Name' });
    fireEvent.change(input, { target: { value: 'nope' } });
    fireEvent.click(within(row('name:ghostname')).getByRole('button', { name: 'Link' }));
    // A failed link keeps the form and the pasted text.
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Not a SoundCloud profile link'));
    expect(input).toHaveValue('nope');

    vi.mocked(linkSuggestion).mockResolvedValueOnce({ ok: true, soundcloud_user_id: '100', display_name: 'Wooli' });
    serverReturns(makeResponse([resolved], [label]));
    fireEvent.change(input, { target: { value: ' https://soundcloud.com/wooli ' } });
    fireEvent.click(within(row('name:ghostname')).getByRole('button', { name: 'Link' }));
    await waitFor(() => expect(screen.queryByText('Ghost Name')).not.toBeInTheDocument());
    expect(linkSuggestion).toHaveBeenLastCalledWith('name:ghostname', 'https://soundcloud.com/wooli');
    expect(toast.success).toHaveBeenCalledWith('Linked to Wooli');
  });

  it('shows labels on their own tab, with "not a label" moving one back', async () => {
    vi.mocked(setSuggestionLabel).mockImplementation(async () => {
      serverReturns(makeResponse([{ ...label, is_label: false }, resolved, unresolved]));
      return { ok: true };
    });
    renderView();
    const tab = await screen.findByRole('tab', { name: /Labels & channels 1/ });
    expect(screen.queryByText('Big Label')).toBeNull();
    fireEvent.click(tab);
    fireEvent.click(within(row('200')).getByRole('button', { name: 'Not a label' }));
    await waitFor(() => expect(screen.getByRole('tab', { name: /Labels & channels 0/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('tab', { name: /Artists/ }));
    expect(row('200')).toBeInTheDocument();
    expect(vi.mocked(setSuggestionLabel).mock.calls[0]).toEqual(['200', false]);
  });

  it('marks an artist as a label, moving it out of the main list', async () => {
    vi.mocked(setSuggestionLabel).mockImplementation(async () => {
      serverReturns(makeResponse([unresolved], [{ ...resolved, is_label: true }, label]));
      return { ok: true };
    });
    renderView();
    await screen.findByText('Wooli');
    fireEvent.click(within(row('100')).getByRole('button', { name: 'This is a label' }));
    await waitFor(() => expect(screen.queryByTestId('account-row-100')).toBeNull());
    expect(screen.getByRole('tab', { name: /Labels & channels 2/ })).toBeInTheDocument();
  });

  it('holds a row\'s actions while a change to that account is in flight', async () => {
    let finish: (v: { ok: true }) => void = () => undefined;
    vi.mocked(setSuggestionLabel).mockReturnValue(new Promise((r) => { finish = r; }));
    renderView();
    await screen.findByText('Wooli');
    fireEvent.click(within(row('name:ghostname')).getByRole('button', { name: 'This is a label' }));
    await waitFor(() => expect(screen.queryByTestId('account-row-name:ghostname')).toBeNull());
    fireEvent.click(screen.getByRole('tab', { name: /Labels & channels/ }));
    const moved = row('name:ghostname');
    expect(within(moved).getByRole('button', { name: 'Dismiss' })).toBeDisabled();
    expect(within(moved).getByRole('button', { name: 'Not a label' })).toBeDisabled();
    fireEvent.click(screen.getByRole('tab', { name: /Artists/ }));
    expect(within(row('100')).getByRole('button', { name: 'Dismiss' })).toBeEnabled();
    await act(async () => { finish({ ok: true }); });
    // The refetch returns the server's unchanged lists: the row is back with artists.
    await waitFor(() => expect(within(row('name:ghostname')).getByRole('button', { name: 'Dismiss' })).toBeEnabled());
  });

  it('shows connections with via chips, and hides the section when the endpoint fails', async () => {
    vi.mocked(getFollowConnections).mockResolvedValue(makeConnections({ co_credit: [makeConnection()] }));
    renderView();
    fireEvent.click(await screen.findByRole('tab', { name: /Connections 1/ }));
    expect(screen.getByText('Works with your top artists')).toBeInTheDocument();
    expect(within(row('300')).getByText('Fav')).toBeInTheDocument();
    expect(screen.queryByText('Your favorites follow')).toBeNull();
  });

  it('hides connections quietly on error', async () => {
    vi.mocked(getFollowConnections).mockRejectedValue(new Error('boom'));
    renderView();
    await screen.findByText('Wooli');
    await waitFor(() => expect(getFollowConnections).toHaveBeenCalled());
    expect(screen.queryByRole('tab', { name: /Connections/ })).toBeNull();
    expect(screen.queryByText('boom')).toBeNull();
  });

  it('tiers untiered follows inline and drops the row', async () => {
    const fresh = makeUntiered({ discovery_artist_id: 8, display_name: 'Fresh' });
    vi.mocked(getUntieredFollows).mockResolvedValue({ recent: [fresh], rated: [makeUntiered()] });
    vi.mocked(updateArtist).mockImplementation(async () => {
      vi.mocked(getUntieredFollows).mockResolvedValue({ recent: [fresh], rated: [] });
      return { id: 7, ranking: 3, tier: 'A' };
    });
    renderView();
    fireEvent.click(await screen.findByRole('tab', { name: /New follows 2/ }));
    const rated = await screen.findByTestId('untiered-row-7');
    expect(within(rated).getByText('50% kept')).toBeInTheDocument();
    expect(within(rated).getByText('4 rated')).toBeInTheDocument();
    expect(within(screen.getByTestId('untiered-row-8')).queryByText(/kept/)).toBeNull();

    fireEvent.click(within(rated).getByRole('button', { name: 'A' }));
    await waitFor(() => expect(screen.queryByTestId('untiered-row-7')).toBeNull());
    expect(vi.mocked(updateArtist).mock.calls[0]).toEqual([7, { tier: 'A' }]);
  });

  it('restores an untiered row when the tier update fails', async () => {
    vi.mocked(getUntieredFollows).mockResolvedValue({ recent: [], rated: [makeUntiered()] });
    vi.mocked(updateArtist).mockRejectedValue(new Error('nope'));
    renderView();
    fireEvent.click(await screen.findByRole('tab', { name: /New follows 1/ }));
    fireEvent.click(within(await screen.findByTestId('untiered-row-7')).getByRole('button', { name: 'S' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('nope'));
    expect(screen.getByTestId('untiered-row-7')).toBeInTheDocument();
  });
});
