import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FilterRule } from '../../api/feedFilters';
import { RuleRow } from './FeedFiltersSection';

const makeRule = (overrides: Partial<FilterRule> = {}): FilterRule => ({
  id: 3,
  name: 'Live set title',
  kind: 'title_regex',
  pattern: 'live at|b2b',
  threshold: null,
  reason: 'live_mix',
  enabled: true,
  seed_key: null,
  created_at: '2026-10-01 00:00:00',
  updated_at: '2026-10-01 00:00:00',
  hits: 20,
  rescues: 3,
  precision: 0.85,
  ...overrides,
});

const renderRow = (rule: FilterRule) => {
  const handlers = { onUpdate: vi.fn(), onDelete: vi.fn() };
  render(<table><tbody><RuleRow rule={rule} {...handlers} /></tbody></table>);
  return handlers;
};

describe('RuleRow', () => {
  it('shows hits, rescues and precision', () => {
    renderRow(makeRule());
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('toggles, edits the pattern on blur and deletes', () => {
    const rule = makeRule();
    const handlers = renderRow(rule);
    fireEvent.click(screen.getByRole('switch', { name: 'Enable Live set title' }));
    expect(handlers.onUpdate).toHaveBeenCalledWith(rule, { enabled: false });

    const field = screen.getByRole('textbox', { name: 'Live set title criterion' });
    fireEvent.change(field, { target: { value: 'boiler room' } });
    fireEvent.blur(field);
    expect(handlers.onUpdate).toHaveBeenCalledWith(rule, { pattern: 'boiler room' });

    fireEvent.click(screen.getByRole('button', { name: 'Delete Live set title' }));
    expect(handlers.onDelete).toHaveBeenCalledWith(rule);
  });

  it('sends a numeric threshold for duration rules and skips unchanged values', () => {
    const rule = makeRule({ kind: 'duration_min', pattern: null, threshold: 15, name: 'Long' });
    const handlers = renderRow(rule);
    const field = screen.getByRole('textbox', { name: 'Long criterion' });
    fireEvent.blur(field);
    expect(handlers.onUpdate).not.toHaveBeenCalled();
    fireEvent.change(field, { target: { value: '30' } });
    fireEvent.keyDown(field, { key: 'Enter' });
    expect(handlers.onUpdate).toHaveBeenCalledWith(rule, { threshold: 30 });
  });
});
