/**
 * The app's single API client.
 *
 * - Base URL from EXPO_PUBLIC_API_URL (set in .env); "/api" is appended here.
 * - Sends the access token; on a 401 it refreshes once with the rotating refresh
 *   token and retries. Concurrent 401s share one refresh call.
 * - When the refresh fails, `onSessionExpired` (set by the auth store) signs out.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';
import type { TokenPair } from '@api-types';

const RAW_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8004').replace(/\/+$/, '');
export const API_URL = RAW_URL.endsWith('/api') ? RAW_URL : `${RAW_URL}/api`;

const ACCESS_KEY = 'scentvault_access_token';
const REFRESH_KEY = 'scentvault_refresh_token';

export const api = axios.create({
  baseURL: API_URL,
  timeout: 15000,
  // Localtunnel shows an HTML interstitial on the first request unless this header is set.
  headers: { 'Content-Type': 'application/json', 'Bypass-Tunnel-Reminder': 'true' },
});

let memoryAccess: string | null = null;

export async function setTokens(access: string, refresh: string): Promise<void> {
  memoryAccess = access;
  await SecureStore.setItemAsync(ACCESS_KEY, access);
  await SecureStore.setItemAsync(REFRESH_KEY, refresh);
}

export async function clearTokens(): Promise<void> {
  memoryAccess = null;
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

export async function getAccessToken(): Promise<string | null> {
  if (memoryAccess) return memoryAccess;
  memoryAccess = await SecureStore.getItemAsync(ACCESS_KEY);
  return memoryAccess;
}

export const getRefreshToken = () => SecureStore.getItemAsync(REFRESH_KEY);

let onSessionExpired: (() => void) | null = null;
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn;
}

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const refresh = await getRefreshToken();
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token: refresh }, {
      headers: { 'Bypass-Tunnel-Reminder': 'true' },
      timeout: 15000,
    });
    await setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch (err) {
    // Only a definite "no" from the server ends the session; offline keeps it.
    if ((err as AxiosError).response?.status === 401) return null;
    throw err;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const isAuthCall = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/register');
    if (error.response?.status === 401 && original && !original._retry && !isAuthCall) {
      original._retry = true;
      refreshing ??= refreshAccess().finally(() => {
        refreshing = null;
      });
      const token = await refreshing.catch(() => undefined);
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      if (token === null) {
        await clearTokens();
        onSessionExpired?.();
      }
    }
    return Promise.reject(error);
  },
);

/** True when the request never reached the server (offline, DNS, timeout). */
export function isNetworkError(err: unknown): boolean {
  const e = err as AxiosError;
  return !!e?.isAxiosError && !e.response;
}

/** Human-readable message from an API error (FastAPI `detail` string or validation list). */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (isNetworkError(err)) return "Can't reach ScentVault — check your connection.";
  const detail = (err as AxiosError<{ detail?: unknown }>)?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: (string | number)[]; msg?: string };
    const field = first.loc?.[first.loc.length - 1];
    return field ? `${field}: ${first.msg}` : first.msg ?? fallback;
  }
  return fallback;
}
