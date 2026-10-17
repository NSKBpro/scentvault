/**
 * Auth store — session, profile and preferences.
 */
import { create } from 'zustand';
import type { MetaOut, PreferencesOut, PreferencesUpdate, TokenPair, UserOut } from '@api-types';
import {
  api,
  clearTokens,
  errorMessage,
  getAccessToken,
  getRefreshToken,
  isNetworkError,
  setSessionExpiredHandler,
  setTokens,
} from '../lib/api';
import { clearAll } from '../lib/offlineDb';
import { registerForPush, unregisterPush } from '../lib/push';

const FALLBACK_META: MetaOut = {
  concentrations: [], genders: [], sillages: [], note_positions: [], radar_axes: [],
  collection_statuses: ['own', 'wishlist', 'tried', 'finished', 'sold', 'gifted'],
  bottle_types: ['full', 'decant', 'sample', 'tester'],
  pick_occasions: ['Office', 'Date Night', 'Casual', 'Gym', 'Evening'],
  currencies: { USD: 1, EUR: 0.92, RSD: 108, GBP: 0.79 },
  ml_per_spray: 0.1,
};

interface AuthState {
  user: UserOut | null;
  prefs: PreferencesOut | null;
  meta: MetaOut;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  loadPrefs: () => Promise<void>;
  updatePrefs: (patch: PreferencesUpdate) => Promise<void>;
  updateProfile: (patch: { display_name?: string; current_password?: string; new_password?: string }) => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => {
  const startSession = async (data: TokenPair) => {
    await setTokens(data.access_token, data.refresh_token);
    set({ user: data.user, isAuthenticated: true, isLoading: false, error: null });
    get().loadPrefs();
    registerForPush().catch(() => undefined);
  };

  setSessionExpiredHandler(() => {
    set({ user: null, prefs: null, isAuthenticated: false, error: 'Your session expired — please sign in again.' });
  });

  return {
    user: null,
    prefs: null,
    meta: FALLBACK_META,
    isAuthenticated: false,
    isLoading: true,
    error: null,

    login: async (email, password) => {
      set({ isLoading: true, error: null });
      try {
        const { data } = await api.post<TokenPair>('/auth/login/json', { email: email.trim(), password });
        await startSession(data);
      } catch (err) {
        set({ error: errorMessage(err, 'Login failed'), isLoading: false });
        throw err;
      }
    },

    register: async (email, password, displayName) => {
      set({ isLoading: true, error: null });
      try {
        const { data } = await api.post<TokenPair>('/auth/register', {
          email: email.trim(), password, display_name: displayName || null,
        });
        await startSession(data);
      } catch (err) {
        set({ error: errorMessage(err, 'Registration failed'), isLoading: false });
        throw err;
      }
    },

    logout: async () => {
      const refresh = await getRefreshToken();
      await unregisterPush().catch(() => undefined);
      api.post('/auth/logout', refresh ? { refresh_token: refresh } : {}).catch(() => undefined);
      await clearTokens();
      await clearAll();
      set({ user: null, prefs: null, isAuthenticated: false, error: null });
    },

    checkAuth: async () => {
      set({ isLoading: true });
      const token = await getAccessToken();
      if (!token) {
        set({ isLoading: false, isAuthenticated: false });
        return;
      }
      try {
        const { data } = await api.get<UserOut>('/auth/me');
        set({ user: data, isAuthenticated: true, isLoading: false });
        get().loadPrefs();
        registerForPush().catch(() => undefined);
      } catch (err) {
        if (isNetworkError(err)) {
          // Offline start: trust the stored session and work from the local cache.
          set({ isAuthenticated: true, isLoading: false });
          return;
        }
        await clearTokens();
        set({ user: null, isAuthenticated: false, isLoading: false });
      }
    },

    loadPrefs: async () => {
      try {
        const [prefs, meta] = await Promise.all([
          api.get<PreferencesOut>('/me/preferences'),
          api.get<MetaOut>('/meta'),
        ]);
        set({ prefs: prefs.data, meta: meta.data });
      } catch {
        /* keep previous values offline */
      }
    },

    updatePrefs: async (patch) => {
      const { data } = await api.patch<PreferencesOut>('/me/preferences', patch);
      set({ prefs: data });
    },

    updateProfile: async (patch) => {
      const { data } = await api.patch<UserOut>('/auth/me', patch);
      set({ user: data });
    },

    clearError: () => set({ error: null }),
  };
});

/** The user's display currency (falls back to EUR until preferences load). */
export const useCurrency = () => useAuthStore((s) => s.prefs?.currency ?? 'EUR');
