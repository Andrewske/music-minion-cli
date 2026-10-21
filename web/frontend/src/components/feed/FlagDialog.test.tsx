import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FlagDialog } from './FlagDialog';

describe('FlagDialog', () => {
  it('renders nothing until a track is targeted', () => {
    render(<FlagDialog target={null} onFlag={vi.fn()} onClose={vi.fn()} />);
    expect(screen.queryByRole('radiogroup', { name: 'Reason' })).not.toBeInTheDocument();
  });

  it('defaults to live mix and flags with the chosen reason and note', () => {
    const onFlag = vi.fn();
    render(<FlagDialog target={{ soundcloudId: '42', title: 'Show 12' }} onFlag={onFlag} onClose={vi.fn()} />);
    expect(screen.getByRole('radio', { name: 'Live mix / set' })).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(screen.getByRole('radio', { name: 'Podcast / radio show' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Flag note' }), { target: { value: 'weekly show' } });
    fireEvent.click(screen.getByRole('button', { name: 'Hide from feed' }));
    expect(onFlag).toHaveBeenCalledWith('42', 'podcast', 'weekly show');
  });
});
