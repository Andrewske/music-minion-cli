import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { useNoteEditor } from './useNoteEditor';

const pending: Array<(value: unknown) => void> = [];
vi.mock('../api/feed', () => ({
  saveFeedNote: vi.fn(() => new Promise((resolve) => pending.push(resolve))),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useNoteEditor', () => {
  it('a slow save for note A does not close note B opened after cancelling A', async () => {
    const { result } = renderHook(() => useNoteEditor(), { wrapper });
    act(() => result.current.open({ soundcloudId: 'A', title: 'A', note: null }));
    act(() => result.current.save('A', 'first'));
    await waitFor(() => expect(pending).toHaveLength(1));
    act(() => result.current.close());
    act(() => result.current.open({ soundcloudId: 'B', title: 'B', note: null }));
    expect(result.current.isSaving).toBe(false);

    await act(async () => pending[0]({ soundcloud_id: 'A', note: 'first', updated_at: 'now' }));
    expect(result.current.target?.soundcloudId).toBe('B');
  });

  it('closes the editor whose own save completed', async () => {
    pending.length = 0;
    const { result } = renderHook(() => useNoteEditor(), { wrapper });
    act(() => result.current.open({ soundcloudId: 'C', title: 'C', note: null }));
    act(() => result.current.save('C', 'done'));
    await waitFor(() => expect(result.current.isSaving).toBe(true));
    await act(async () => pending[0]({ soundcloud_id: 'C', note: 'done', updated_at: 'now' }));
    expect(result.current.target).toBeNull();
  });
});
