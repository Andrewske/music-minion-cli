import { useQuery } from '@tanstack/react-query';
import { getStats } from '../api/stats';

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}