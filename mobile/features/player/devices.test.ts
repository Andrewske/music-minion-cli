import { describe, expect, it } from 'vitest';
import type { Device } from '@music-minion/shared';
import { activeDeviceName, otherDeviceRows, playerSecondLine, FALLBACK_DEVICE_NAME } from './devices';

const device = (id: string, name: string): Device => ({ id, name, connected_at: '2026-10-23T00:00:00Z' });
const devices = [device('phone', 'Pixel'), device('laptop', 'Kevin laptop'), device('pi', 'Living room')];

describe('activeDeviceName', () => {
  it('returns the active device name', () => {
    expect(activeDeviceName(devices, 'laptop')).toBe('Kevin laptop');
  });

  it('falls back when the id is unknown or null', () => {
    expect(activeDeviceName(devices, 'gone')).toBe(FALLBACK_DEVICE_NAME);
    expect(activeDeviceName(devices, null)).toBe(FALLBACK_DEVICE_NAME);
  });

  it('falls back on a blank name', () => {
    expect(activeDeviceName([device('x', '  ')], 'x')).toBe(FALLBACK_DEVICE_NAME);
  });
});

describe('playerSecondLine', () => {
  it('shows the artist when this device plays', () => {
    const line = playerSecondLine({ isThisDeviceActive: true, artist: 'Rezz', devices, activeDeviceId: 'phone' });
    expect(line).toEqual({ text: 'Rezz', isRemote: false });
  });

  it('shows Unknown Artist when there is no artist', () => {
    const line = playerSecondLine({ isThisDeviceActive: true, artist: undefined, devices, activeDeviceId: 'phone' });
    expect(line.text).toBe('Unknown Artist');
  });

  it('names the remote device', () => {
    const line = playerSecondLine({ isThisDeviceActive: false, artist: 'Rezz', devices, activeDeviceId: 'laptop' });
    expect(line).toEqual({ text: 'on Kevin laptop', isRemote: true });
  });

  it('uses the fallback for an unlisted remote device', () => {
    const line = playerSecondLine({ isThisDeviceActive: false, artist: 'Rezz', devices: [], activeDeviceId: 'laptop' });
    expect(line.text).toBe('on another device');
  });
});

describe('otherDeviceRows', () => {
  it('drops this device and puts the active one first', () => {
    expect(otherDeviceRows(devices, 'phone', 'pi')).toEqual([
      { id: 'pi', name: 'Living room', isActive: true },
      { id: 'laptop', name: 'Kevin laptop', isActive: false },
    ]);
  });

  it('marks nothing active when this device plays', () => {
    const rows = otherDeviceRows(devices, 'phone', 'phone');
    expect(rows.map((r) => r.isActive)).toEqual([false, false]);
  });

  it('names blank devices', () => {
    expect(otherDeviceRows([device('a', '')], 'phone', null)[0]?.name).toBe('Unnamed device');
  });

  it('is empty when only this device is connected', () => {
    expect(otherDeviceRows([device('phone', 'Pixel')], 'phone', 'phone')).toEqual([]);
  });
});
