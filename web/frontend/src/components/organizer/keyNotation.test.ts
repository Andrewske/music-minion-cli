import { describe, expect, it } from 'vitest';
import { formatKey, fromCamelot, toCamelot } from './keyNotation';

describe('toCamelot', () => {
  it.each([
    ['C', '8B'], ['C#', '3B'], ['Db', '3B'], ['E', '12B'], ['B', '1B'], ['F#', '2B'],
    ['Am', '8A'], ['Ebm', '2A'], ['Abm', '1A'], ['G#m', '1A'], ['C#m', '12A'], ['Em', '9A'],
  ])('%s -> %s', (key, code) => {
    expect(toCamelot(key)).toBe(code);
  });

  it('rejects non-keys', () => {
    expect(toCamelot('H')).toBeNull();
    expect(toCamelot('7A')).toBeNull();
  });
});

describe('fromCamelot', () => {
  it('maps both wheels', () => {
    expect(fromCamelot('7A')).toBe('Dm');
    expect(fromCamelot('3B')).toBe('C#');
    expect(fromCamelot('12a')).toBe('C#m');
  });

  it('rejects out-of-range codes', () => {
    expect(fromCamelot('13A')).toBeNull();
    expect(fromCamelot('0B')).toBeNull();
  });
});

describe('formatKey', () => {
  it('shows musical then Camelot for either stored notation', () => {
    expect(formatKey('C#')).toBe('C# / 3B');
    expect(formatKey('Ebm')).toBe('Ebm / 2A');
    expect(formatKey('7A')).toBe('Dm / 7A');
  });

  it('round-trips every Camelot code', () => {
    for (let n = 1; n <= 12; n++) {
      for (const letter of ['A', 'B']) {
        const musical = fromCamelot(`${n}${letter}`);
        expect(musical && toCamelot(musical)).toBe(`${n}${letter}`);
      }
    }
  });

  it('falls back to the raw value or a dash', () => {
    expect(formatKey('weird')).toBe('weird');
    expect(formatKey(undefined)).toBe('–');
  });
});
