import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createApiClient, ApiError } from '../api/client.js';

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

describe('createApiClient', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('constructs URLs with the given base', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'test' }),
    });

    const client = createApiClient('http://my-server:8642/api');
    await client.request('/health');

    expect(mockFetch).toHaveBeenCalledWith(
      'http://my-server:8642/api/health',
      expect.any(Object)
    );
  });

  it('works with relative base URL (web)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });

    const client = createApiClient('/api');
    await client.request('/playlists');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/playlists',
      expect.any(Object)
    );
  });

  it('throws ApiError on non-ok response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: () => Promise.resolve({ detail: 'Playlist not found' }),
    });

    const client = createApiClient('/api');
    await expect(client.request('/playlists/999')).rejects.toThrow(ApiError);
    await expect(client.request('/playlists/999')).rejects.toThrow('Playlist not found');
  });

  it('falls back to statusText when response body is not JSON', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('not json')),
    });

    const client = createApiClient('/api');
    await expect(client.request('/crash')).rejects.toThrow('Internal Server Error');
  });

  it('post() sends JSON body', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 1 }),
    });

    const client = createApiClient('/api');
    await client.post('/playlists', { name: 'Test' });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/playlists',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Test' }),
      })
    );
  });

  it('getBaseUrl() returns the configured base', () => {
    const client = createApiClient('http://tailscale:8642/api');
    expect(client.getBaseUrl()).toBe('http://tailscale:8642/api');
  });
});
