import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BucketSession, SessionSummary } from '../../api/buckets';
import { listSessions } from '../../api/buckets';
import { SessionSwitcher } from './SessionSwitcher';

vi.mock('../../api/buckets', () => ({ listSessions: vi.fn() }));

const listMock = vi.mocked(listSessions);

beforeAll(() => {
  // Radix popper measures its content; jsdom has no ResizeObserver.
  globalThis.ResizeObserver = class {
    observe(): void { /* noop */ }
    unobserve(): void { /* noop */ }
    disconnect(): void { /* noop */ }
  };
});

const session: BucketSession = {
  id: 's1', playlist_id: 1, status: 'active', name: 'Dubstep split',
  created_at: '2026-11-03 10:00:00', buckets: [], unassigned_track_ids: [],
};

const row = (id: string, name: string | null, status: SessionSummary['status'], buckets: number, assigned: number): SessionSummary => ({
  id, playlist_id: 1, name, status, created_at: '2026-10-20 10:00:00', last_opened_at: null,
  bucket_count: buckets, assigned_count: assigned,
});

interface Handlers {
  onNew: ReturnType<typeof vi.fn>;
  onSwitch: ReturnType<typeof vi.fn>;
  onRename: ReturnType<typeof vi.fn>;
  onDelete: ReturnType<typeof vi.fn>;
  onFinish: ReturnType<typeof vi.fn>;
}

async function renderOpen(isDiscovery = false): Promise<Handlers> {
  const handlers: Handlers = { onNew: vi.fn(), onSwitch: vi.fn(), onRename: vi.fn(), onDelete: vi.fn(), onFinish: vi.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SessionSwitcher playlistId={1} session={session} isDiscovery={isDiscovery} isBusy={false} {...handlers} />
    </QueryClientProvider>
  );
  expect(listMock).not.toHaveBeenCalled(); // lazy until opened
  await act(async () => {
    fireEvent.keyDown(screen.getByRole('button', { name: 'Switch organizer session' }), { key: 'Enter' });
  });
  await screen.findByText('Session · Oct 20');
  return handlers;
}

describe('SessionSwitcher', () => {
  beforeEach(() => {
    listMock.mockReset();
    listMock.mockResolvedValue([
      row('s1', 'Dubstep split', 'active', 4, 88),
      row('s2', null, 'parked', 3, 41),
      row('s3', 'Vibes', 'applied', 2, 12),
    ]);
  });

  it('lists other sessions with counts and marks applied ones done', async () => {
    await renderOpen();
    expect(listMock).toHaveBeenCalledWith(1);
    expect(screen.getByText('4 buckets · 88')).toBeInTheDocument();
    expect(screen.getByText('3 buckets · 41')).toBeInTheDocument();
    expect(screen.getByText('(done)')).toBeInTheDocument();
  });

  it('switches when another session is picked', async () => {
    const { onSwitch } = await renderOpen();
    fireEvent.click(screen.getByText('Vibes'));
    expect(onSwitch).toHaveBeenCalledWith('s3');
  });

  it('asks before deleting', async () => {
    const { onDelete } = await renderOpen();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete Session · Oct 20' }));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(onDelete).toHaveBeenCalledWith('s2');
  });

  it('renames the current session inline', async () => {
    const { onRename } = await renderOpen();
    fireEvent.click(screen.getByTitle('Rename session'));
    const input = screen.getByRole('textbox', { name: 'Session name' });
    fireEvent.change(input, { target: { value: 'Peak time' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onRename).toHaveBeenCalledWith('s1', 'Peak time');
  });

  it('needs a second click to finish and warns on discovery playlists', async () => {
    const { onFinish } = await renderOpen(true);
    expect(screen.getByText(/likes tracks in linked buckets on SoundCloud/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Finish session'));
    expect(onFinish).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Click again to finish'));
    expect(onFinish).toHaveBeenCalled();
  });

  it('starts a new session', async () => {
    const { onNew } = await renderOpen();
    fireEvent.click(screen.getByText('New session'));
    expect(onNew).toHaveBeenCalled();
  });
});
