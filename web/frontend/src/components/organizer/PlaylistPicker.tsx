import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ListPlus, Plus } from 'lucide-react';
import { usePlaylists } from '../../hooks/usePlaylists';
import { addTrackToPlaylist, createPlaylist, getTrackPlaylists, removeTrackFromPlaylist } from '../../api/playlists';
import { canCreatePlaylist, filterPlaylists } from './playlistPicker';
import { SearchPicker, type PickerOption } from './SearchPicker';

type PlaylistChoice = { kind: 'existing'; id: number; name: string } | { kind: 'create'; name: string };

/** Organizing feeds the local (Serato-bound) playlists, whatever library the session is in. */
const TARGET_LIBRARY = 'local';

interface PlaylistPickerProps {
  trackId: number;
  /** The playlist being organized; hidden so the track can't be pulled out from under the session. */
  excludePlaylistId: number;
}

/** Adds the track to the playlist, or removes it when it's already there. */
async function togglePlaylist(trackId: number, choice: PlaylistChoice, isMember: boolean): Promise<void> {
  if (choice.kind === 'existing' && isMember) {
    await removeTrackFromPlaylist(choice.id, trackId);
    return;
  }
  const playlistId = choice.kind === 'create' ? (await createPlaylist(choice.name, '', TARGET_LIBRARY)).id : choice.id;
  await addTrackToPlaylist(playlistId, trackId);
}

export function PlaylistPicker({ trackId, excludePlaylistId }: PlaylistPickerProps): JSX.Element {
  const queryClient = useQueryClient();
  const { data: playlists = [] } = usePlaylists(TARGET_LIBRARY);
  const membershipKey = ['track-playlists', trackId];
  const { data: memberships = [] } = useQuery({
    queryKey: membershipKey,
    queryFn: () => getTrackPlaylists(trackId),
  });
  const memberIds = new Set(memberships.map((p) => p.id));
  const count = memberships.filter((p) => p.id !== excludePlaylistId).length;

  const getOptions = (query: string): PickerOption<PlaylistChoice>[] => [
    ...filterPlaylists(playlists, query, memberIds, excludePlaylistId).map((p) => ({
      key: String(p.id),
      label: p.name,
      value: { kind: 'existing', id: p.id, name: p.name } as const,
      icon: <Check className={`w-3.5 h-3.5 shrink-0 ${memberIds.has(p.id) ? 'text-emerald-400' : 'invisible'}`} />,
      meta: p.track_count,
    })),
    ...(canCreatePlaylist(playlists, query)
      ? [{ key: 'create', label: `Create playlist "${query.trim()}"`, value: { kind: 'create', name: query.trim() } as const, icon: <Plus className="w-3.5 h-3.5 shrink-0" /> }]
      : []),
  ];

  const choose = async (choice: PlaylistChoice): Promise<boolean> => {
    const isMember = choice.kind === 'existing' && memberIds.has(choice.id);
    try {
      await togglePlaylist(trackId, choice, isMember);
    } catch (err) {
      const action = isMember ? 'remove track from' : 'add track to';
      throw new Error(`Couldn't ${action} "${choice.name}": ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      void queryClient.invalidateQueries({ queryKey: membershipKey });
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
    }
    return false; // stay open so several playlists can be toggled in a row
  };

  return (
    <SearchPicker
      trigger={
        <>
          <ListPlus className="w-3.5 h-3.5" />
          {count > 0 ? `In ${count} playlist${count === 1 ? '' : 's'}` : 'Add to playlist'}
        </>
      }
      triggerTitle="Add to or remove from local playlists"
      triggerClassName="flex items-center gap-1 px-2 py-1 rounded-sm text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors"
      placeholder="Search or create a local playlist…"
      emptyText="No manual playlists match. Type a name to create one."
      getOptions={getOptions}
      onChoose={choose}
      align="right"
    />
  );
}
