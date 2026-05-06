import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from 'react';

export type AudioKey = 'A' | 'B';

interface AudioElementContextValue {
  audioA: HTMLAudioElement | null;
  audioB: HTMLAudioElement | null;
  activeKey: AudioKey;
  activeKeyRef: MutableRefObject<AudioKey>;
  setActiveKey: (key: AudioKey) => void;
}

const AudioElementContext = createContext<AudioElementContextValue | null>(null);

export function AudioElementProvider({ children }: { children: ReactNode }): JSX.Element {
  const [audioA, setAudioA] = useState<HTMLAudioElement | null>(null);
  const [audioB, setAudioB] = useState<HTMLAudioElement | null>(null);
  const activeKeyRef = useRef<AudioKey>('A');
  const [activeKey, setActiveKeyState] = useState<AudioKey>('A');

  const setActiveKey = useCallback((k: AudioKey): void => {
    activeKeyRef.current = k;
    setActiveKeyState(k);
  }, []);

  const value = useMemo<AudioElementContextValue>(
    () => ({ audioA, audioB, activeKey, activeKeyRef, setActiveKey }),
    [audioA, audioB, activeKey, setActiveKey],
  );

  return (
    <AudioElementContext.Provider value={value}>
      <audio ref={setAudioA} preload="auto" style={{ display: 'none' }} />
      <audio ref={setAudioB} preload="auto" style={{ display: 'none' }} />
      {children}
    </AudioElementContext.Provider>
  );
}

function useAudioContext(): AudioElementContextValue {
  const ctx = useContext(AudioElementContext);
  if (!ctx) {
    throw new Error('useAudioContext must be used within AudioElementProvider');
  }
  return ctx;
}

/**
 * Returns the audio element currently serving as the active playback target.
 * Subscribes to `activeKey` state, so consumers re-render on swap.
 * Used by PlayerBar progress polling and WaveformPlayer.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useActiveAudioElement(): HTMLAudioElement | null {
  const { audioA, audioB, activeKey } = useAudioContext();
  return activeKey === 'A' ? audioA : audioB;
}

interface AudioPair {
  audioA: HTMLAudioElement | null;
  audioB: HTMLAudioElement | null;
  activeKeyRef: MutableRefObject<AudioKey>;
  setActiveKey: (key: AudioKey) => void;
}

/**
 * Returns audio elements and the activeKey ref/setter for usePlayer's effects.
 * Effects must read `activeKeyRef.current` and OMIT it from dependency arrays
 * to avoid swap-back loops.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useAudioPair(): AudioPair {
  const { audioA, audioB, activeKeyRef, setActiveKey } = useAudioContext();
  return { audioA, audioB, activeKeyRef, setActiveKey };
}
