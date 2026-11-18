import { describe, expect, it } from 'vitest';
import { shortcutFor } from './useComparisonShortcuts';

const key = (k: string, mods: Partial<Record<'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey', boolean>> = {}) => ({
  key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...mods,
});

describe('shortcutFor', () => {
  it('maps 1 and 2 to picking deck A and B', () => {
    expect(shortcutFor(key('1'))).toEqual({ kind: 'pick', slot: 'a' });
    expect(shortcutFor(key('2'))).toEqual({ kind: 'pick', slot: 'b' });
  });

  it('maps Tab to flip but leaves Shift+Tab for focus navigation', () => {
    expect(shortcutFor(key('Tab'))).toEqual({ kind: 'flip' });
    expect(shortcutFor(key('Tab', { shiftKey: true }))).toBeNull();
  });

  it('maps S and Z regardless of case', () => {
    expect(shortcutFor(key('s'))).toEqual({ kind: 'skip' });
    expect(shortcutFor(key('Z', { shiftKey: true }))).toEqual({ kind: 'undo' });
  });

  it('ignores modified keys and keys PlayerBar owns', () => {
    expect(shortcutFor(key('z', { ctrlKey: true }))).toBeNull();
    expect(shortcutFor(key('1', { metaKey: true }))).toBeNull();
    expect(shortcutFor(key(' '))).toBeNull();
    expect(shortcutFor(key('ArrowRight'))).toBeNull();
  });
});
