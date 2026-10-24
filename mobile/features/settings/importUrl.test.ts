import { describe, expect, it } from 'vitest';
import { importEndpoint } from './importUrl';

describe('importEndpoint', () => {
  it('routes YouTube links', () => {
    expect(importEndpoint('https://www.youtube.com/watch?v=abc')).toBe('/youtube/import');
    expect(importEndpoint(' https://youtu.be/abc ')).toBe('/youtube/import');
  });

  it('routes SoundCloud links', () => {
    expect(importEndpoint('https://soundcloud.com/artist/track')).toBe('/soundcloud/import');
  });

  it('rejects anything else', () => {
    expect(importEndpoint('https://open.spotify.com/track/1')).toBeNull();
    expect(importEndpoint('')).toBeNull();
  });
});
