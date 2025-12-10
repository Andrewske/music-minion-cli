import { apiRequest } from './client';
import type { StatsResponse } from '../types';

export async function getStats(): Promise<StatsResponse> {
  return apiRequest<StatsResponse>('/stats');
}