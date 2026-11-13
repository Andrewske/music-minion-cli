import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type JSX, type ReactNode } from 'react';
import { NOTES_AUTOSAVE_MS, useTrackNotes } from './useTrackNotes';

const getTrackNotes = vi.fn((id: number) => Promise.resolve({ notes: `server ${id}` }));
const saveTrackNotes = vi.fn((_id: number, notes: string) => Promise.resolve({ notes }));

vi.mock('../api/tracks', () => ({
  getTrackNotes: (id: number) => getTrackNotes(id),
  saveTrackNotes: (id: number, notes: string) => saveTrackNotes(id, notes),
}));

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

async function settle(): Promise<void> {
  await act(async () => {
    await vi.runAllTimersAsync();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  getTrackNotes.mockClear();
  saveTrackNotes.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useTrackNotes', () => {
  it('loads the file comment into the draft', async () => {
    const { result } = renderHook(() => useTrackNotes(1, true), { wrapper });
    await settle();
    expect(result.current.draft).toBe('server 1');
  });

  it('autosaves once typing pauses', async () => {
    const { result } = renderHook(() => useTrackNotes(1, true), { wrapper });
    await settle();
    act(() => result.current.setDraft('a'));
    act(() => result.current.setDraft('ab'));
    expect(result.current.status).toBe('pending');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NOTES_AUTOSAVE_MS);
    });
    expect(saveTrackNotes).toHaveBeenCalledTimes(1);
    expect(saveTrackNotes).toHaveBeenCalledWith(1, 'ab');
    expect(result.current.status).toBe('saved');
  });

  it('flush saves immediately and only once', async () => {
    const { result } = renderHook(() => useTrackNotes(1, true), { wrapper });
    await settle();
    act(() => result.current.setDraft('blurred'));
    act(() => result.current.flush());
    await settle();
    expect(saveTrackNotes).toHaveBeenCalledTimes(1);
    expect(saveTrackNotes).toHaveBeenCalledWith(1, 'blurred');
  });

  it('saves the previous track when the track changes mid-edit', async () => {
    const { result, rerender } = renderHook(({ id }) => useTrackNotes(id, true), {
      wrapper,
      initialProps: { id: 1 },
    });
    await settle();
    act(() => result.current.setDraft('half typed'));
    rerender({ id: 2 });
    await settle();
    expect(saveTrackNotes).toHaveBeenCalledWith(1, 'half typed');
    expect(result.current.draft).toBe('server 2');
  });

  it('keeps a failed save pending so the next flush retries it', async () => {
    saveTrackNotes.mockRejectedValueOnce(new Error('disk full'));
    const { result } = renderHook(() => useTrackNotes(1, true), { wrapper });
    await settle();
    act(() => result.current.setDraft('retry me'));
    act(() => result.current.flush());
    await settle();
    expect(result.current.status).toBe('error');
    act(() => result.current.flush());
    await settle();
    expect(saveTrackNotes).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe('saved');
  });
});
