import '@testing-library/jest-dom';

// jsdom doesn't always provide localStorage in Node 24+ (depending on jsdom version
// and bun/node interaction). Provide a minimal in-memory shim so module-load-time
// reads from createWebStorageAdapter() don't crash before tests run.
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.getItem !== 'function') {
  const memory = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string): string | null => memory.get(key) ?? null,
      setItem: (key: string, value: string): void => {
        memory.set(key, value);
      },
      removeItem: (key: string): void => {
        memory.delete(key);
      },
      clear: (): void => {
        memory.clear();
      },
      key: (index: number): string | null => Array.from(memory.keys())[index] ?? null,
      get length(): number {
        return memory.size;
      },
    },
  });
}
