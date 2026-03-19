/**
 * Web API client — initializes shared client with web defaults.
 * All API modules now live in @music-minion/shared.
 */
import { createApiClient, setDefaultApiClient } from '@music-minion/shared';

const API_BASE = '/api';

const webApiClient = createApiClient(API_BASE);
setDefaultApiClient(webApiClient);

// Re-export for backward compat with any direct imports
export { ApiError, getDefaultApiClient } from '@music-minion/shared';
export const apiRequest = webApiClient.request;
