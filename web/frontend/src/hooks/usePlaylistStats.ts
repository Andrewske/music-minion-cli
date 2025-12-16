import { useQuery } from '@tanstack/react-query';
import { getPlaylistStats } from '../api/playlists';

export function usePlaylistStats(playlistId: number | null) {
  return useQuery({
    queryKey: ['playlist-stats', playlistId],
    queryFn: () => {
      if (!playlistId) throw new Error('Playlist ID is required');
      return getPlaylistStats(playlistId);
    },
    enabled: !!playlistId,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}