import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import { decideCleanup, getPendingCleanup, getPendingCleanupCount } from '../api/cleanup';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

describe('cleanup API', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('reads the pending rows and the badge count', async () => {
    await getPendingCleanup();
    await getPendingCleanupCount();
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual(['/api/cleanup/pending', '/api/cleanup/pending/count']);
  });

  it('posts one decision with its edited tags', async () => {
    const expected = { title: 'Song (R Flip)', credited_artists: ['A'], remixers: ['R'] };
    await decideCleanup({ id: '2026/x.mp3', verdict: 'edited', expected });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/cleanup/pending/decision');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ id: '2026/x.mp3', verdict: 'edited', expected });
  });
});
