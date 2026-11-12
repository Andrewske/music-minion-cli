import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import {
  dismissSuggestion, followAccount, getFollowConnections, getFollowSuggestions,
  getUntieredFollows, setSuggestionLabel,
} from '../api/followSuggestions';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const lastCall = (): [string, RequestInit] => fetchMock.mock.calls[0] as [string, RequestInit];

describe('follow suggestions api', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: true }) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('GETs the list, untiered, and connections endpoints', async () => {
    await getFollowSuggestions();
    await getUntieredFollows();
    await getFollowConnections();
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      '/api/follow-suggestions',
      '/api/follow-suggestions/untiered',
      '/api/follow-suggestions/connections',
    ]);
  });

  it('URL-encodes name keys when dismissing', async () => {
    await dismissSuggestion('name:dirt monkey/x');
    const [url, init] = lastCall();
    expect(url).toBe('/api/follow-suggestions/name%3Adirt%20monkey%2Fx/dismiss');
    expect(init.method).toBe('POST');
  });

  it('POSTs is_label for label overrides', async () => {
    await setSuggestionLabel('123', false);
    const [url, init] = lastCall();
    expect(url).toBe('/api/follow-suggestions/123/label');
    expect(JSON.parse(init.body as string)).toEqual({ is_label: false });
  });

  it('POSTs follow by SoundCloud user id', async () => {
    await followAccount('987');
    const [url, init] = lastCall();
    expect(url).toBe('/api/follow-suggestions/987/follow');
    expect(init.method).toBe('POST');
  });

  it('surfaces the server detail on failure', async () => {
    fetchMock.mockResolvedValue({
      ok: false, status: 502, statusText: 'Bad Gateway',
      json: () => Promise.resolve({ detail: 'SoundCloud follow failed' }),
    });
    await expect(followAccount('1')).rejects.toThrow('SoundCloud follow failed');
  });
});
