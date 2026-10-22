import type { CleanupRow, PendingCleanupResponse } from '../../api/cleanup';

/** Test fixture: a pending row where run B adds a guest artist. */
export function makeRow(id: string, overrides: Partial<CleanupRow> = {}): CleanupRow {
  return {
    id,
    current: { title: 'Artist - Song (R FLIP)', credited_artists: ['R'], remixers: [] },
    a: { title: 'Song (R Flip)', credited_artists: ['Artist'], remixers: ['R'] },
    b: { title: 'Song (R Flip)', credited_artists: ['Artist', 'Guest'], remixers: ['R'] },
    diff: { title: false, credited_artists: true, remixers: false },
    confidence: 0.7,
    notes: 'Assuming Guest is featured',
    raw: { title: `Raw ${id}`, uploader: 'R', description: 'free dl', filename: 'Song', url: 'https://soundcloud.com/r/song' },
    unclear: false,
    track_id: 7,
    ...overrides,
  };
}

export const makePage = (...ids: string[]): PendingCleanupResponse => ({ rows: ids.map((id) => makeRow(id)), count: ids.length });
