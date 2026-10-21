import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FlaggedItem } from '../../api/feedFilters';
import { FlaggedRow } from './FlaggedList';
import { describeFlag, formatFlagDuration, ruleErrorMessage } from './flagged';

const makeItem = (overrides: Partial<FlaggedItem> = {}): FlaggedItem => ({
  flag_id: 9,
  soundcloud_id: '42',
  reason: 'live_mix',
  source: 'rule',
  rule_id: 1,
  rule_name: 'Longer than 15 min',
  created_at: '2026-10-01T12:00:00Z',
  local_track_id: null,
  title: 'Live at Fabric',
  artist_name: 'Some DJ',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 3_725_000,
  access: 'playable',
  note: null,
  ...overrides,
});

const renderRow = (item: FlaggedItem) => {
  const handlers = { onPlay: vi.fn(), onUnflag: vi.fn() };
  render(<FlaggedRow item={item} isPlaying={false} isUpdating={false} {...handlers} />);
  return handlers;
};

describe('FlaggedRow', () => {
  it('shows the rule that caught a track and offers Rescue', () => {
    const handlers = renderRow(makeItem());
    expect(screen.getByText(/Live mix \/ set · Longer than 15 min/)).toBeInTheDocument();
    expect(screen.getByText('1:02:05')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rescue Live at Fabric' }));
    expect(handlers.onUnflag).toHaveBeenCalledWith(expect.objectContaining({ soundcloud_id: '42' }));
    fireEvent.click(screen.getByRole('button', { name: 'Play Live at Fabric' }));
    expect(handlers.onPlay).toHaveBeenCalled();
  });

  it('offers Un-flag with the note for user flags', () => {
    renderRow(makeItem({ source: 'user', rule_id: null, rule_name: null, reason: 'podcast', note: 'weekly' }));
    expect(screen.getByRole('button', { name: 'Un-flag Live at Fabric' })).toBeInTheDocument();
    expect(screen.getByText(/weekly/)).toBeInTheDocument();
  });
});

describe('flag helpers', () => {
  it('describes each flag source', () => {
    expect(describeFlag({ reason: 'other', source: 'user', rule_name: null })).toBe('Other');
    expect(describeFlag({ reason: 'podcast', source: 'rule', rule_name: null })).toBe('Podcast / radio show · deleted rule');
    expect(describeFlag({ reason: 'live_mix', source: 'agent', rule_name: null })).toBe('Live mix / set · agent');
  });

  it('formats durations with hours only when needed', () => {
    expect(formatFlagDuration(125_000)).toBe('2:05');
  });

  it('surfaces server validation messages only when they are text', () => {
    expect(ruleErrorMessage(new Error("Invalid regex '(': missing ), unterminated subpattern at position 0"), 'x')).toMatch(/^Invalid regex/);
    expect(ruleErrorMessage(new Error('[object Object]'), 'fallback')).toBe('fallback');
    expect(ruleErrorMessage('nope', 'fallback')).toBe('fallback');
  });
});
