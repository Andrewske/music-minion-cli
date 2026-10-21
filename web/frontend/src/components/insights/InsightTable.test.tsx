import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { InsightRow } from '../../api/insights';
import { InsightTable } from './InsightTable';

const rows: InsightRow[] = [
  { value: 'vip', seen: 12, keeps: 6, not_quites: 2, nopes: 4, keep_pct: 58.3, lift: 33.8 },
  { value: 'radio show', seen: 9, keeps: 0, not_quites: 0, nopes: 9, keep_pct: 0, lift: -24.5 },
];

describe('InsightTable', () => {
  it('shows seen, keep % and signed lift per value', () => {
    render(<InsightTable label="Title keyword" rows={rows} selectedValue={null} onSelect={vi.fn()} />);
    const table = screen.getByRole('table', { name: 'Title keyword insights' });
    const [, first, second] = within(table).getAllByRole('row');
    expect(within(first).getByText('vip')).toBeInTheDocument();
    expect(within(first).getByText('12')).toBeInTheDocument();
    expect(within(first).getByText('58.3%')).toBeInTheDocument();
    expect(within(first).getByText('+33.8 pts')).toBeInTheDocument();
    expect(within(second).getByText('-24.5 pts')).toBeInTheDocument();
  });

  it('selects a row to list its tracks', () => {
    const onSelect = vi.fn();
    render(<InsightTable label="Title keyword" rows={rows} selectedValue="vip" onSelect={onSelect} />);
    expect(screen.getByRole('button', { name: 'vip' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'radio show' }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
  });
});
