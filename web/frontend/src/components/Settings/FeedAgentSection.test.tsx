import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FeedClassification, RuleSuggestion } from '../../api/feedAgent';
import { ClassificationRow, SuggestionRow, UnreadableNotice } from './FeedAgentSection';
import { suggestionOverrides } from './feedAgent';

vi.mock('../../hooks/usePlayFeedRow', () => ({ usePlayFeedRow: () => vi.fn() }));

const suggestion: RuleSuggestion = {
  id: 4,
  signature: 'title_regex:\\bradio\\W+show\\b',
  name: 'Title has "radio show"',
  kind: 'title_regex',
  pattern: '\\bradio\\W+show\\b',
  threshold: null,
  reason: 'podcast',
  support: 14,
  counter: 1,
  evidence: '14 of your 20 flags contain "radio show"; 1 real track would also be caught',
  status: 'pending',
  rule_id: null,
};

const classification: FeedClassification = {
  id: 9,
  soundcloud_id: '42',
  model_id: 'jev',
  mix_probability: 0.72,
  podcast_probability: 0.1,
  status: 'pending',
  created_at: '2026-10-20 00:00:00',
  local_track_id: null,
  title: 'Sunset Session',
  uploader: 'Some DJ',
  genre: 'House',
  tags: [],
  duration_ms: 600_000,
  artwork_url: null,
  permalink_url: null,
  access: 'playable',
};

describe('suggestionOverrides', () => {
  it('sends nothing when untouched and only edited fields otherwise', () => {
    expect(suggestionOverrides(suggestion, suggestion.pattern ?? '', 'podcast')).toBeUndefined();
    expect(suggestionOverrides(suggestion, ' radio ', 'live_mix')).toEqual({ pattern: 'radio', reason: 'live_mix' });
    const duration = { ...suggestion, kind: 'duration_min' as const, pattern: null, threshold: 10 };
    expect(suggestionOverrides(duration, '12', 'podcast')).toEqual({ threshold: 12 });
  });
});

describe('SuggestionRow', () => {
  it('shows the evidence and accepts with edits or dismisses', () => {
    const onAccept = vi.fn();
    const onDismiss = vi.fn();
    render(<SuggestionRow suggestion={suggestion} isBusy={false} onAccept={onAccept} onDismiss={onDismiss} />);
    expect(screen.getByText(/14 of your 20 flags/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: `${suggestion.name} criterion` }), { target: { value: 'radio show' } });
    fireEvent.click(screen.getByRole('button', { name: /Accept/ }));
    expect(onAccept).toHaveBeenCalledWith(suggestion, { pattern: 'radio show' });
    fireEvent.click(screen.getByRole('button', { name: /Dismiss/ }));
    expect(onDismiss).toHaveBeenCalledWith(suggestion);
  });
});

describe('ClassificationRow', () => {
  it('shows Jev confidence and resolves either way', () => {
    const onResolve = vi.fn();
    render(<ClassificationRow item={classification} isBusy={false} onPlay={vi.fn()} onResolve={onResolve} />);
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('10:00')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Filter Sunset Session' }));
    expect(onResolve).toHaveBeenCalledWith(classification, true);
    fireEvent.click(screen.getByRole('button', { name: 'Keep Sunset Session in feed' }));
    expect(onResolve).toHaveBeenCalledWith(classification, false);
  });
});

describe('UnreadableNotice', () => {
  it('is hidden with nothing unreadable', () => {
    const { container } = render(<UnreadableNotice count={0} isRetrying={false} onRetry={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the count and retries', () => {
    const onRetry = vi.fn();
    render(<UnreadableNotice count={3} isRetrying={false} onRetry={onRetry} />);
    expect(screen.getByText(/3 tracks got unreadable answers/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Retry unreadable/ }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
