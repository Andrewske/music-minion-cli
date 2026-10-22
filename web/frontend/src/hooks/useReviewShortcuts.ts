import { useEffect, useRef } from 'react';
import type { CleanupVerdict } from '../api/cleanup';

export interface ReviewShortcutActions {
  move: (delta: 1 | -1) => void;
  decide: (verdict: CleanupVerdict) => void;
  edit: () => void;
  play: () => void;
}

/** Same keys as the CLI review page (review.html, apply mode). */
export function shortcutFor(key: string, actions: ReviewShortcutActions): (() => void) | null {
  const map: Record<string, () => void> = {
    j: () => actions.move(1), ArrowDown: () => actions.move(1),
    k: () => actions.move(-1), ArrowUp: () => actions.move(-1),
    1: () => actions.decide('model'), 3: () => actions.decide('alt'), 2: () => actions.decide('gold'),
    u: () => actions.decide('unclear'), x: () => actions.decide('exclude'),
    e: actions.edit, p: actions.play,
  };
  return map[key] ?? null;
}

const isTyping = (target: EventTarget | null): boolean =>
  target instanceof HTMLElement && (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable);

/** Global keydown handler while the Tag review page is mounted; inactive while typing. */
export function useReviewShortcuts(actions: ReviewShortcutActions, enabled: boolean): void {
  const latest = useRef(actions);
  useEffect(() => {
    latest.current = actions;
  });
  useEffect(() => {
    if (!enabled) return undefined;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      const run = shortcutFor(event.key, latest.current);
      if (!run) return;
      event.preventDefault();
      run();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enabled]);
}
