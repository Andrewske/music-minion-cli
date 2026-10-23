import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import { formatTrackLabel, lookupTracks } from '../api/tracks';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

describe('lookupTracks', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('POSTs the ids to /tracks/lookup', async () => {
    await lookupTracks([3, 1]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/tracks/lookup');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ ids: [3, 1] });
  });

  it('skips the request for an empty list', async () => {
    expect(await lookupTracks([])).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('formatTrackLabel', () => {
  it('joins artist and title', () => {
    expect(formatTrackLabel({ id: 1, title: 'Song', artist: 'Band' })).toBe('Band — Song');
  });

  it('falls back when fields are missing', () => {
    expect(formatTrackLabel({ id: 7, title: 'Song', artist: null })).toBe('Song');
    expect(formatTrackLabel({ id: 7, title: ' ', artist: 'Band' })).toBe('Band — Track #7');
  });
});
