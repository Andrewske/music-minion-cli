import { describe, it, expect } from 'vitest';
import { createMemoryStorageAdapter } from '../stores/storage.js';

describe('createMemoryStorageAdapter', () => {
  it('returns null for missing keys', () => {
    const storage = createMemoryStorageAdapter();
    expect(storage.getItem('missing')).toBeNull();
  });

  it('stores and retrieves values', () => {
    const storage = createMemoryStorageAdapter();
    storage.setItem('key', 'value');
    expect(storage.getItem('key')).toBe('value');
  });

  it('overwrites existing values', () => {
    const storage = createMemoryStorageAdapter();
    storage.setItem('key', 'first');
    storage.setItem('key', 'second');
    expect(storage.getItem('key')).toBe('second');
  });

  it('removes values', () => {
    const storage = createMemoryStorageAdapter();
    storage.setItem('key', 'value');
    storage.removeItem('key');
    expect(storage.getItem('key')).toBeNull();
  });

  it('isolates between adapter instances', () => {
    const a = createMemoryStorageAdapter();
    const b = createMemoryStorageAdapter();
    a.setItem('key', 'a');
    b.setItem('key', 'b');
    expect(a.getItem('key')).toBe('a');
    expect(b.getItem('key')).toBe('b');
  });
});
