/**
 * DI-based API client. Both web and mobile create their own instance
 * with platform-appropriate baseUrl.
 *
 * Web:    createApiClient('/api')
 * Mobile: createApiClient('http://my-server.tailnet.ts.net:8642/api')
 */

export class ApiError extends Error {
  public status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface ApiClient {
  request: <T>(endpoint: string, options?: RequestInit) => Promise<T>;
  post: <T>(endpoint: string, body?: unknown) => Promise<T>;
  getBaseUrl: () => string;
}

export const createApiClient = (baseUrl: string): ApiClient => {
  const request = async <T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> => {
    const url = `${baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers ?? {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(response.status, errorData.detail || response.statusText);
    }

    return response.json();
  };

  const post = async <T>(endpoint: string, body?: unknown): Promise<T> => {
    const init: RequestInit = { method: 'POST' };
    if (body) init.body = JSON.stringify(body);
    return request<T>(endpoint, init);
  };

  const getBaseUrl = (): string => baseUrl;

  return { request, post, getBaseUrl };
};

/**
 * Singleton for backward compat during migration.
 * Web sets this on app init; shared API modules use it as default.
 */
let defaultClient: ApiClient | null = null;

export const setDefaultApiClient = (client: ApiClient): void => {
  defaultClient = client;
};

export const getDefaultApiClient = (): ApiClient => {
  if (!defaultClient) {
    throw new Error(
      'API client not initialized. Call setDefaultApiClient() at app startup.'
    );
  }
  return defaultClient;
};
