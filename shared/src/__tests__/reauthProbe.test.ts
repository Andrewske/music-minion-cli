import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  isReauthDetail,
  probeStreamForReauth,
  SOUNDCLOUD_REAUTH_DETAIL,
} from '../playback/reauthProbe.js';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const jsonResponse = (status: number, body: unknown): Partial<Response> => ({
  status,
  json: () => Promise.resolve(body),
});

describe('isReauthDetail', () => {
  it('matches the reauth detail', () => {
    expect(isReauthDetail({ detail: SOUNDCLOUD_REAUTH_DETAIL })).toBe(true);
  });

  it('rejects other details', () => {
    expect(isReauthDetail({ detail: 'stream_unavailable' })).toBe(false);
  });

  it('rejects non-object bodies', () => {
    expect(isReauthDetail(null)).toBe(false);
    expect(isReauthDetail('soundcloud_reauth_required')).toBe(false);
    expect(isReauthDetail(undefined)).toBe(false);
  });
});

describe('probeStreamForReauth', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('returns true for a 503 with the reauth detail', async () => {
    mockFetch.mockResolvedValue(jsonResponse(503, { detail: SOUNDCLOUD_REAUTH_DETAIL }));
    await expect(probeStreamForReauth('/api/tracks/1/stream')).resolves.toBe(true);
  });

  it('returns false for a 503 with another detail', async () => {
    mockFetch.mockResolvedValue(jsonResponse(503, { detail: 'other' }));
    await expect(probeStreamForReauth('/api/tracks/1/stream')).resolves.toBe(false);
  });

  it('returns false for a healthy stream (non-503) and aborts the download', async () => {
    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      const signal = init.signal;
      return Promise.resolve({
        status: 200,
        json: () => Promise.reject(new Error('should not parse body')),
        get aborted() {
          return signal?.aborted ?? false;
        },
      });
    });
    await expect(probeStreamForReauth('/api/tracks/1/stream')).resolves.toBe(false);
    const init = mockFetch.mock.calls[0][1] as RequestInit;
    expect(init.signal?.aborted).toBe(true);
  });

  it('returns false when the probe itself fails (falls back to normal policy)', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));
    await expect(probeStreamForReauth('/api/tracks/1/stream')).resolves.toBe(false);
  });

  it('returns false for a 503 whose body is not JSON', async () => {
    mockFetch.mockResolvedValue({
      status: 503,
      json: () => Promise.reject(new SyntaxError('not json')),
    });
    await expect(probeStreamForReauth('/api/tracks/1/stream')).resolves.toBe(false);
  });

  it('returns false when the probe times out', async () => {
    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new Error('aborted')));
      });
    });
    await expect(probeStreamForReauth('/api/tracks/1/stream', 10)).resolves.toBe(false);
  });
});
