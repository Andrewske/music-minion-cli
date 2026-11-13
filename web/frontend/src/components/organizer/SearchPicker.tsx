import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

export interface PickerOption<T> {
  key: string;
  label: string;
  value: T;
  icon?: ReactNode;
  meta?: ReactNode;
}

interface SearchPickerProps<T> {
  trigger: ReactNode;
  triggerTitle: string;
  triggerClassName: string;
  placeholder: string;
  emptyText: string;
  getOptions: (query: string) => PickerOption<T>[];
  /** Resolve true to close after choosing; throw to show the error in the dropdown. */
  onChoose: (value: T) => Promise<boolean>;
  onOpen?: () => void;
  align?: 'left' | 'right';
  optionClassName?: string;
}

function useOutsideClose(open: boolean, close: () => void): React.RefObject<HTMLDivElement | null> {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open, close]);
  return ref;
}

/** Trigger button plus a type-to-search dropdown with arrow-key navigation. */
export function SearchPicker<T>(props: SearchPickerProps<T>): JSX.Element {
  const { trigger, triggerTitle, triggerClassName, placeholder, onOpen, align = 'left' } = props;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = useCallback((): void => setOpen(false), []);
  const containerRef = useOutsideClose(open, close);
  const options = open ? props.getOptions(query) : [];

  const toggleOpen = (): void => {
    if (!open) {
      setQuery('');
      setActive(0);
      setError(null);
      onOpen?.();
    }
    setOpen(!open);
  };

  const choose = async (option: PickerOption<T>): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      if (await props.onChoose(option.value)) setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => Math.min(Math.max(i + step, 0), Math.max(options.length - 1, 0)));
    } else if (e.key === 'Enter' && options[active] && !busy) {
      e.preventDefault();
      void choose(options[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative inline-flex">
      <button type="button" onClick={toggleOpen} aria-expanded={open} title={triggerTitle} className={triggerClassName}>
        {trigger}
      </button>
      {open && (
        <div
          className={`absolute top-full mt-1 z-30 w-64 max-w-[calc(100vw-2rem)] bg-obsidian-surface border border-obsidian-border rounded-lg shadow-lg overflow-hidden ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={handleKeyDown}
            disabled={busy}
            placeholder={placeholder}
            className="w-full px-3 py-2 bg-black/40 border-b border-white/10 text-sm text-white/90 placeholder:text-white/30 focus:outline-hidden"
          />
          <OptionList
            options={options}
            active={active}
            emptyText={props.emptyText}
            optionClassName={props.optionClassName ?? ''}
            onHover={setActive}
            onChoose={(option) => void choose(option)}
          />
          {error && <div className="px-3 py-2 text-xs text-red-400 border-t border-white/10">{error}</div>}
        </div>
      )}
    </div>
  );
}

interface OptionListProps<T> {
  options: PickerOption<T>[];
  active: number;
  emptyText: string;
  optionClassName: string;
  onHover: (index: number) => void;
  onChoose: (option: PickerOption<T>) => void;
}

function OptionList<T>({ options, active, emptyText, optionClassName, onHover, onChoose }: OptionListProps<T>): JSX.Element {
  if (options.length === 0) {
    return <div className="px-3 py-2 text-xs text-white/40">{emptyText}</div>;
  }
  return (
    <ul role="listbox" className="max-h-64 overflow-y-auto py-1">
      {options.map((option, i) => (
        <li key={option.key} role="option" aria-selected={i === active}>
          <button
            type="button"
            onMouseEnter={() => onHover(i)}
            onClick={() => onChoose(option)}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm ${optionClassName} ${
              i === active ? 'bg-white/10 text-white' : 'text-white/70'
            }`}
          >
            {option.icon}
            <span className="flex-1 truncate">{option.label}</span>
            {option.meta && <span className="text-xs text-white/30">{option.meta}</span>}
          </button>
        </li>
      ))}
    </ul>
  );
}
