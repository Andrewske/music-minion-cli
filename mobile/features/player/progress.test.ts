import { describe, expect, it } from 'vitest';
import { clampToDuration, playbackPositionSec, progressFraction } from './progress';

const base = { isThisDeviceActive: false, localPositionSec: 0, remotePositionMs: 0, durationSec: 300 };

describe('playbackPositionSec', () => {
  it('uses RNTP position when this device plays', () => {
    expect(playbackPositionSec({ ...base, isThisDeviceActive: true, localPositionSec: 12.5, remotePositionMs: 90000 })).toBe(12.5);
  });

  it('uses the store position when another device plays', () => {
    expect(playbackPositionSec({ ...base, remotePositionMs: 90000 })).toBe(90);
  });

  it('clamps negative and non-finite values to 0', () => {
    expect(playbackPositionSec({ ...base, remotePositionMs: -500 })).toBe(0);
    expect(playbackPositionSec({ ...base, isThisDeviceActive: true, localPositionSec: Number.NaN })).toBe(0);
  });

  it('stops a stale remote extrapolation at the track end', () => {
    // Device-check repro: 15:39 elapsed on a 2:13 track.
    expect(playbackPositionSec({ ...base, remotePositionMs: 939_000, durationSec: 133 })).toBe(133);
  });

  it('clamps the local position to the duration too', () => {
    expect(playbackPositionSec({ ...base, isThisDeviceActive: true, localPositionSec: 134, durationSec: 133 })).toBe(133);
  });

  it('passes the position through when the duration is unknown', () => {
    expect(playbackPositionSec({ ...base, remotePositionMs: 939_000, durationSec: undefined })).toBe(939);
    expect(playbackPositionSec({ ...base, remotePositionMs: 939_000, durationSec: 0 })).toBe(939);
  });
});

describe('clampToDuration', () => {
  it('caps at a known duration and leaves shorter positions alone', () => {
    expect(clampToDuration(200, 120)).toBe(120);
    expect(clampToDuration(60, 120)).toBe(60);
  });

  it('ignores unusable durations', () => {
    expect(clampToDuration(60, Number.NaN)).toBe(60);
    expect(clampToDuration(60, -1)).toBe(60);
  });
});

describe('progressFraction', () => {
  it('divides position by duration', () => {
    expect(progressFraction(30, 120)).toBe(0.25);
  });

  it('clamps to 0..1', () => {
    expect(progressFraction(200, 120)).toBe(1);
    expect(progressFraction(-5, 120)).toBe(0);
  });

  it('is 0 without a usable duration', () => {
    expect(progressFraction(30, undefined)).toBe(0);
    expect(progressFraction(30, 0)).toBe(0);
    expect(progressFraction(Number.POSITIVE_INFINITY, 120)).toBe(0);
  });
});
