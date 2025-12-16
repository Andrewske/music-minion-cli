import { useQuery } from '@tanstack/react-query';
import type { Playlist } from '../types';

export function usePlaylists() {
  return useQuery({
    queryKey: ['playlists'],
    queryFn: async (): Promise<Playlist[]> => {
      const response = await fetch('/api/playlists');
      if (!response.ok) {
        throw new Error('Failed to fetch playlists');
      }
      const data = await response.json();
      return data.playlists;
    },
  });
}