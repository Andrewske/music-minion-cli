import { createContext, useContext, useRef, type RefObject, type ReactNode } from 'react';

const AudioElementContext = createContext<RefObject<HTMLAudioElement> | null>(null);

export function AudioElementProvider({ children }: { children: ReactNode }): JSX.Element {
  const audioRef = useRef<HTMLAudioElement>(null);
  return (
    <AudioElementContext.Provider value={audioRef}>
      <audio ref={audioRef} preload="auto" style={{ display: 'none' }} />
      {children}
    </AudioElementContext.Provider>
  );
}

export function useAudioElement(): HTMLAudioElement | null {
  const ref = useContext(AudioElementContext);
  if (!ref) {
    throw new Error('useAudioElement must be used within AudioElementProvider');
  }
  return ref.current;
}
