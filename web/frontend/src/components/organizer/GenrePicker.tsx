import { ChevronDown, Plus } from 'lucide-react';
import { useGenreStore } from '../../stores/genreStore';
import { createGenre, getTrackGenres, updateTrackGenres } from '../../api/genres';
import { canCreateGenre, filterGenres, normalizeGenreName, withPrimaryGenre } from './genrePicker';
import { SearchPicker, type PickerOption } from './SearchPicker';

type GenreChoice = { kind: 'existing'; id: number; name: string } | { kind: 'create'; name: string };

interface GenrePickerProps {
  trackId: number;
  genre: string | null | undefined;
  /** Called with the track's new primary genre after a successful save. */
  onChange: (genre: string | null) => void;
}

/** Sets the track's primary genre; any secondary genres stay behind it. */
async function savePrimaryGenre(trackId: number, choice: GenreChoice): Promise<string | null> {
  const genreId = choice.kind === 'create' ? (await createGenre(choice.name)).id : choice.id;
  const current = await getTrackGenres(trackId);
  const updated = await updateTrackGenres(trackId, withPrimaryGenre(current.map((g) => g.id), genreId));
  return updated[0]?.name ?? null;
}

export function GenrePicker({ trackId, genre, onChange }: GenrePickerProps): JSX.Element {
  const { genres, fetchGenres } = useGenreStore();

  // tracks.genre holds the file's casing ("Drum & Bass"); genre names are lowercased
  const current = normalizeGenreName(genre ?? '');

  const getOptions = (query: string): PickerOption<GenreChoice>[] => {
    const name = normalizeGenreName(query);
    return [
      ...filterGenres(genres, query).map((g) => ({
        key: String(g.id),
        label: g.name,
        value: { kind: 'existing', id: g.id, name: g.name } as const,
        meta: g.name === current ? '✓' : g.track_count,
      })),
      ...(canCreateGenre(genres, query)
        ? [{ key: 'create', label: `Create "${name}"`, value: { kind: 'create', name } as const, icon: <Plus className="w-3.5 h-3.5 shrink-0" /> }]
        : []),
    ];
  };

  const choose = async (choice: GenreChoice): Promise<boolean> => {
    try {
      onChange(await savePrimaryGenre(trackId, choice));
    } catch (err) {
      throw new Error(`Couldn't save genre "${choice.name}": ${err instanceof Error ? err.message : String(err)}`);
    }
    void fetchGenres();
    return true;
  };

  return (
    <SearchPicker
      trigger={
        <>
          {genre || 'Add genre'}
          <ChevronDown className="w-3 h-3 opacity-60" />
        </>
      }
      triggerTitle="Change genre"
      triggerClassName={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-sm capitalize transition-colors ${
        genre ? 'text-white/70 bg-white/10 hover:bg-white/15' : 'text-white/35 hover:text-white/60 hover:bg-white/5'
      }`}
      placeholder="Search or create a genre…"
      emptyText="No genres yet. Type to create one."
      getOptions={getOptions}
      onChoose={choose}
      onOpen={() => void fetchGenres()}
      optionClassName="capitalize"
    />
  );
}
