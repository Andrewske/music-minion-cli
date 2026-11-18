import { useEffect, useRef } from 'react';

export interface ComparisonShortcutHandlers {
  onPick: (slot: 'a' | 'b') => void;
  onFlip: () => void;
  onSkip: () => void;
  onUndo: () => void;
}

/** True when the key belongs to a text field, an open menu, or a dialog. */
function isTypingOrInOverlay(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return true;
  return target.closest('[role="menu"], [role="dialog"], [role="listbox"]') !== null;
}

/** Map a keydown to a comparison action; null for keys this page doesn't own. */
export function shortcutFor(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey'>):
  | { kind: 'pick'; slot: 'a' | 'b' }
  | { kind: 'flip' | 'skip' | 'undo' }
  | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  if (event.key === 'Tab') return event.shiftKey ? null : { kind: 'flip' };
  switch (event.key.toLowerCase()) {
    case '1': return { kind: 'pick', slot: 'a' };
    case '2': return { kind: 'pick', slot: 'b' };
    case 's': return { kind: 'skip' };
    case 'z': return { kind: 'undo' };
    default: return null;
  }
}

/**
 * Page shortcuts: 1/2 pick, Tab flips decks at the same position, S skips,
 * Z undoes. Space and ←/→ stay with PlayerBar. `enabled` is false when
 * there's no pair on screen or an overlay (Stats) is open, which also gives
 * Tab back to focus navigation.
 */
export function useComparisonShortcuts(handlers: ComparisonShortcutHandlers, enabled: boolean): void {
  // Refs so the listener binds once and always sees the latest values
  const handlersRef = useRef(handlers);
  const enabledRef = useRef(enabled);
  useEffect(() => {
    handlersRef.current = handlers;
    enabledRef.current = enabled;
  }, [handlers, enabled]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (!enabledRef.current || event.repeat || isTypingOrInOverlay(event.target)) return;
      const action = shortcutFor(event);
      if (!action) return;
      event.preventDefault();
      const h = handlersRef.current;
      if (action.kind === 'pick') h.onPick(action.slot);
      else if (action.kind === 'flip') h.onFlip();
      else if (action.kind === 'skip') h.onSkip();
      else h.onUndo();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
