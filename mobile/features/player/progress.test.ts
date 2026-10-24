import { describe, expect, it } from 'vitest';
import { playbackPositionSec, progressFraction } from './progress';

describe('playbackPositionSec', () => {
  it('uses RNTP position when this device plays', () => {
    expect(playbackPositionSec({ isThisDeviceActive: true, localPositionSec: 12.5, remotePositionMs: 90000 })).toBe(12.5);
  });

  it('uses the store position when another device plays', () => {
    expect(playbackPositionSec({ isThisDeviceActive: false, localPositionSec: 0, remotePositionMs: 90000 })).toBe(90);
  });

  it('clamps negative and non-finite values to 0', () => {
    expect(playbackPositionSec({ isThisDeviceActive: false, localPositionSec: 0, remotePositionMs: -500 })).toBe(0);
    expect(playbackPositionSec({ isThisDeviceActive: true, localPositionSec: Number.NaN, remotePositionMs: 0 })).toBe(0);
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
