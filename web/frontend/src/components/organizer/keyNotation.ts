// Camelot wheel, indexed by number - 1. Spellings follow the library's tags.
const CAMELOT_MAJOR = ['B', 'F#', 'C#', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E'];
const CAMELOT_MINOR = ['Abm', 'Ebm', 'Bbm', 'Fm', 'Cm', 'Gm', 'Dm', 'Am', 'Em', 'Bm', 'F#m', 'C#m'];

const PITCH_CLASS: Record<string, number> = {
  C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, F: 5, 'F#': 6, Gb: 6,
  G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11,
};

/** Camelot code ("3B") for a musical key ("C#", "Ebm"), or null if unrecognized. */
export function toCamelot(key: string): string | null {
  const match = /^([A-G][#b]?)(m|min)?$/.exec(key.trim());
  const pc = match ? PITCH_CLASS[match[1]] : undefined;
  if (!match || pc === undefined) return null;
  const minor = Boolean(match[2]);
  // Majors step a fifth (7 semitones) per number from C = 8B; minors use their relative major
  const majorPc = minor ? (pc + 3) % 12 : pc;
  return `${((7 * majorPc + 7) % 12) + 1}${minor ? 'A' : 'B'}`;
}

/** Musical key ("Dm") for a Camelot code ("7A"), or null if unrecognized. */
export function fromCamelot(code: string): string | null {
  const match = /^(1[0-2]|[1-9])([AB])$/i.exec(code.trim());
  if (!match) return null;
  const wheel = match[2].toUpperCase() === 'A' ? CAMELOT_MINOR : CAMELOT_MAJOR;
  return wheel[Number(match[1]) - 1];
}

/** "C# / 3B" from either notation; anything unrecognized is shown as stored. */
export function formatKey(key: string | undefined): string {
  if (!key?.trim()) return '–';
  const camelot = toCamelot(key);
  if (camelot) return `${key.trim()} / ${camelot}`;
  const musical = fromCamelot(key);
  return musical ? `${musical} / ${key.trim().toUpperCase()}` : key;
}
