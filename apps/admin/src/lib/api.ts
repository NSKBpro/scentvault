/**
 * The admin's single API client.
 *
 * - Base URL from VITE_API_URL (default http://127.0.0.1:8004/api)
 * - Adds the access token to every request
 * - On 401, refreshes once with the refresh token (rotating) and retries;
 *   concurrent 401s share a single refresh call
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type { TokenPair } from '@api-types';
import { clearSession, getAccessToken, getRefreshToken, saveSession } from './auth';

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8004/api';

const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token: refresh });
    saveSession(data);
    return data.access_token;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const isAuthCall = original?.url?.includes('/auth/');
    if (error.response?.status === 401 && original && !original._retry && !isAuthCall) {
      original._retry = true;
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null;
      });
      const token = await refreshing;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      clearSession();
      if (window.location.pathname !== '/login') window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

/** Human-readable message from an API error (FastAPI detail string or validation list). */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const detail = (err as AxiosError<{ detail?: unknown }>)?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.') || 'field'}: ${d.msg}`)
      .join('; ');
  }
  if ((err as AxiosError)?.message === 'Network Error') return 'Cannot reach the API — is it running?';
  return fallback;
}

export default api;
