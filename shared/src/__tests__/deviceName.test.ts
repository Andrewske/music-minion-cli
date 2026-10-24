import { describe, expect, it } from 'vitest';
import { defaultDeviceName, deviceIdSuffix, resolveDeviceName } from '../stores/deviceName';

describe('deviceIdSuffix', () => {
  it('takes the first four alphanumerics, lowercased', () => {
    expect(deviceIdSuffix('3F2A9c1e-0000-4000-8000-000000000000')).toBe('3f2a');
    expect(deviceIdSuffix('-a-b-c-d-e')).toBe('abcd');
  });

  it('is empty for an id with no alphanumerics', () => {
    expect(deviceIdSuffix('')).toBe('');
    expect(deviceIdSuffix('----')).toBe('');
  });
});

describe('defaultDeviceName', () => {
  it('appends the id suffix to the label', () => {
    expect(defaultDeviceName('Pixel 9 Pro', '3f2a9c1e-x')).toBe('Pixel 9 Pro (3f2a)');
  });

  it('gives two same-model devices different names', () => {
    const a = defaultDeviceName('Android Phone', 'aaaa1111');
    const b = defaultDeviceName('Android Phone', 'bbbb2222');
    expect(a).not.toBe(b);
  });

  it('falls back when the label is blank or the id has no usable chars', () => {
    expect(defaultDeviceName('  ', 'abcd')).toBe('Unknown device (abcd)');
    expect(defaultDeviceName('macOS Chrome', '')).toBe('macOS Chrome');
  });
});

describe('resolveDeviceName', () => {
  it('keeps a persisted custom name untouched', () => {
    expect(resolveDeviceName('Android Phone', 'Pixel 9 Pro', 'abcd')).toBe('Android Phone');
    expect(resolveDeviceName('Kevin laptop', 'macOS Chrome', 'abcd')).toBe('Kevin laptop');
  });

  it('uses the default when no custom name is stored', () => {
    expect(resolveDeviceName(null, 'Pixel 9 Pro', 'abcd')).toBe('Pixel 9 Pro (abcd)');
    expect(resolveDeviceName('   ', 'Pixel 9 Pro', 'abcd')).toBe('Pixel 9 Pro (abcd)');
  });
});
