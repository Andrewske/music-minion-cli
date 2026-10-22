import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { shortcutFor } from '../../hooks/useReviewShortcuts';
import { CleanupCard, type CleanupCardProps } from './CleanupCard';
import { makeRow } from './cleanupTestRows';

function renderCard(overrides: Partial<CleanupCardProps> = {}): CleanupCardProps {
  const props: CleanupCardProps = {
    row: makeRow('2026/x.mp3'),
    isActive: true, isEditing: false, isPlaying: false,
    onActivate: vi.fn(), onDecide: vi.fn(), onEdit: vi.fn(), onPlay: vi.fn(),
    ...overrides,
  };
  render(<CleanupCard {...props} />);
  return props;
}

describe('CleanupCard', () => {
  it('shows current, A and B with changed cells and the A/B disagreement marked', () => {
    renderCard();
    expect(screen.getByTestId('cell-credited_artists-b')).toHaveAttribute('data-changed', 'true');
    expect(screen.getByTestId('cell-credited_artists-current')).toHaveAttribute('data-changed', 'false');
    expect(screen.getByText('Guest').tagName).toBe('MARK');
    expect(screen.getAllByText('A ≠ B')).toHaveLength(1);
    expect(screen.getByRole('link', { name: /SoundCloud/ })).toHaveAttribute('href', 'https://soundcloud.com/r/song');
  });

  it('sends each verdict from its button', () => {
    const props = renderCard();
    const clicks: Array<[string, string]> = [['Use A', 'model'], ['Use B', 'alt'], ['Keep current', 'gold'], ['Unclear', 'unclear'], ['Skip', 'exclude']];
    for (const [label] of clicks) fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));
    expect(vi.mocked(props.onDecide).mock.calls.map((call) => call[0])).toEqual(clicks.map(([, verdict]) => verdict));
    fireEvent.click(screen.getByRole('button', { name: /Edit/ }));
    expect(props.onEdit).toHaveBeenCalledWith(true);
  });

  it('saves the edit form, prefilled from A, as edited', () => {
    const props = renderCard({ isEditing: true });
    const artists = screen.getByLabelText(/Artists/);
    expect(artists).toHaveValue('Artist');
    fireEvent.change(artists, { target: { value: 'Artist; Guest ' } });
    fireEvent.click(screen.getByRole('button', { name: /Save edit/ }));
    expect(props.onDecide).toHaveBeenCalledWith('edited', { title: 'Song (R Flip)', credited_artists: ['Artist', 'Guest'], remixers: ['R'] });
  });

  it('disables play when the file is not in the library yet', () => {
    renderCard({ row: makeRow('y', { track_id: null }) });
    expect(screen.getByRole('button', { name: /Play/ })).toBeDisabled();
  });
});

describe('review shortcuts', () => {
  it('match review.html: 1 = A, 3 = B, 2 = keep, u, x, e, p, j/k', () => {
    const actions = { move: vi.fn(), decide: vi.fn(), edit: vi.fn(), play: vi.fn() };
    for (const key of ['1', '3', '2', 'u', 'x', 'e', 'p', 'j', 'k']) shortcutFor(key, actions)?.();
    expect(actions.decide.mock.calls.map((call) => call[0])).toEqual(['model', 'alt', 'gold', 'unclear', 'exclude']);
    expect(actions.edit).toHaveBeenCalledOnce();
    expect(actions.play).toHaveBeenCalledOnce();
    expect(actions.move.mock.calls).toEqual([[1], [-1]]);
    expect(shortcutFor('q', actions)).toBeNull();
  });
});
