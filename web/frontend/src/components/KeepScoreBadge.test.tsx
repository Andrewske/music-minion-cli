import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KeepScoreBadge } from './KeepScoreBadge';

describe('KeepScoreBadge', () => {
  it('renders nothing for an unscored track', () => {
    const { container } = render(<KeepScoreBadge probability={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('rounds to a percent and turns green from 70%', () => {
    render(<KeepScoreBadge probability={0.726} modelVersion="jev-v2" />);
    const badge = screen.getByText('73%');
    expect(badge).toHaveClass('text-emerald-300');
    expect(badge).toHaveAttribute('title', 'Predicted keep probability (jev-v2)');
  });
});
