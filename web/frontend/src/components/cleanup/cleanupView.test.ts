import { describe, expect, it } from 'vitest';
import { makePage as page, makeRow } from './cleanupTestRows';
import {
  applyOptimisticDecision,
  cellChanged,
  cellTokens,
  diffTokens,
  draftFromView,
  groupWords,
  rollbackDecision,
  runsDisagree,
  viewFromDraft,
} from './cleanupView';

describe('diff highlighting', () => {
  it('marks list names missing from the baseline', () => {
    expect(diffTokens(['Artist', 'Guest'], ['Artist'])).toEqual([
      { text: 'Artist', changed: false },
      { text: 'Guest', changed: true },
    ]);
  });

  it('marks title words that differ, case included', () => {
    expect(diffTokens('Song (R Flip)', 'Artist - Song (R FLIP)').map((t) => [t.text, t.changed])).toEqual([
      ['Song', false], ['(R', false], ['Flip)', true],
    ]);
  });

  it('merges runs of changed title words into one highlight', () => {
    expect(groupWords(diffTokens('Walk It Talk It (hxrdy VIP)', 'walk it talk it (hxrdy vip)'))).toEqual([
      { text: 'Walk It Talk It', changed: true },
      { text: '(hxrdy', changed: false },
      { text: 'VIP)', changed: true },
    ]);
  });

  it('compares A and B against current, never current against itself', () => {
    const row = makeRow('x');
    expect(cellTokens(row, 'credited_artists', 'current').every((t) => !t.changed)).toBe(true);
    expect(cellTokens(row, 'credited_artists', 'b').map((t) => t.changed)).toEqual([true, true]);
    expect(cellChanged(row, 'title', 'current')).toBe(false);
    expect(cellChanged(row, 'remixers', 'a')).toBe(true);
    expect(cellChanged(makeRow('y', { a: makeRow('y').current }), 'title', 'a')).toBe(false);
  });

  it('flags fields where the two runs disagree', () => {
    const row = makeRow('x');
    expect(runsDisagree(row, 'credited_artists')).toBe(true);
    expect(runsDisagree(row, 'title')).toBe(false);
  });
});

describe('edit draft', () => {
  it('round-trips names through "; " text and drops blanks', () => {
    const draft = draftFromView(makeRow('x').b);
    expect(draft.credited_artists).toBe('Artist; Guest');
    expect(viewFromDraft({ ...draft, title: '  New  ', remixers: ' ; X ;' })).toEqual({
      title: 'New', credited_artists: ['Artist', 'Guest'], remixers: ['X'],
    });
  });
});

describe('optimistic decisions', () => {
  it('removes a decided row and remembers where it was', () => {
    const result = applyOptimisticDecision(page('a', 'b', 'c'), 'b', 'model');
    expect(result.data.rows.map((r) => r.id)).toEqual(['a', 'c']);
    expect(result.data.count).toBe(2);
    expect(result.removed?.index).toBe(1);
  });

  it('moves an unclear row to the end, still pending', () => {
    const result = applyOptimisticDecision(page('a', 'b', 'c'), 'a', 'unclear');
    expect(result.data.rows.map((r) => [r.id, r.unclear])).toEqual([['b', false], ['c', false], ['a', true]]);
    expect(result.data.count).toBe(3);
  });

  it('ignores an id that is not in the list', () => {
    const data = page('a');
    expect(applyOptimisticDecision(data, 'zzz', 'gold')).toEqual({ data, removed: null });
  });

  it('rolls a failed decision back into its old slot', () => {
    const { data, removed } = applyOptimisticDecision(page('a', 'b', 'c'), 'b', 'alt');
    if (!removed) throw new Error('expected a removed row');
    const restored = rollbackDecision(data, removed);
    expect(restored.rows.map((r) => r.id)).toEqual(['a', 'b', 'c']);
    expect(restored.count).toBe(3);
  });

  it('rolls an unclear move back without duplicating the row', () => {
    const { data, removed } = applyOptimisticDecision(page('a', 'b'), 'a', 'unclear');
    if (!removed) throw new Error('expected a removed row');
    const restored = rollbackDecision(data, removed);
    expect(restored.rows.map((r) => [r.id, r.unclear])).toEqual([['a', false], ['b', false]]);
    expect(restored.count).toBe(2);
  });
});
