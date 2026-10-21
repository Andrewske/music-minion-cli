import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { NoteDialog } from './NoteDialog';

describe('NoteDialog', () => {
  it('renders nothing until a track is targeted', () => {
    render(<NoteDialog target={null} onSave={vi.fn()} onClose={vi.fn()} />);
    expect(screen.queryByRole('textbox', { name: 'Track note' })).not.toBeInTheDocument();
  });

  it('starts from the saved note and saves the edited text', () => {
    const onSave = vi.fn();
    render(
      <NoteDialog
        target={{ soundcloudId: '42', title: 'Signal Path', note: 'too long' }}
        onSave={onSave}
        onClose={vi.fn()}
      />
    );
    const field = screen.getByRole('textbox', { name: 'Track note' });
    expect(field).toHaveValue('too long');
    fireEvent.change(field, { target: { value: 'vocals' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledWith('42', 'vocals');
  });

  it('closes on cancel without saving', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<NoteDialog target={{ soundcloudId: '42', title: null, note: null }} onSave={onSave} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });
});
