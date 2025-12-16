import { useQuery } from '@tanstack/react-query';
import { getPlaylistTracks } from '../api/playlists';

export function usePlaylistTracks(playlistId: number | null) {
  return useQuery({
    queryKey: ['playlist-tracks', playlistId],
    queryFn: () => {
      if (!playlistId) throw new Error('Playlist ID is required');
      return getPlaylistTracks(playlistId);
    },
    enabled: !!playlistId,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}