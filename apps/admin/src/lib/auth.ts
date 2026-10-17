import type { TokenPair, UserOut } from '@api-types';

const ACCESS = 'sv_access';
const REFRESH = 'sv_refresh';
const USER = 'sv_user';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const getAccessToken = () => read(ACCESS);
export const getRefreshToken = () => read(REFRESH);

export function getUser(): UserOut | null {
  const raw = read(USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserOut;
  } catch {
    return null;
  }
}

export function saveSession(pair: TokenPair): void {
  try {
    localStorage.setItem(ACCESS, pair.access_token);
    localStorage.setItem(REFRESH, pair.refresh_token);
    localStorage.setItem(USER, JSON.stringify(pair.user));
  } catch {
    /* storage unavailable: session lives until reload */
  }
}

export function clearSession(): void {
  try {
    [ACCESS, REFRESH, USER, 'token'].forEach((k) => localStorage.removeItem(k));
  } catch {
    /* ignore */
  }
}

export const isAuthenticated = () => !!getAccessToken() && getUser()?.role === 'admin';
