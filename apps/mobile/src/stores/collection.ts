/**
 * Collection + wear-log store (offline-first).
 *
 * Reads come from the SQLite cache immediately, then a sync refreshes them.
 * Writes go to the API when online; when not, they are applied locally and
 * queued in the outbox with a client_ref so a later replay can't duplicate.
 */
import { create } from 'zustand';
import type { AxiosResponse } from 'axios';
import type {
  BottleType,
  CollectionItemIn,
  CollectionItemOut,
  CollectionItemUpdate,
  CollectionStatus,
  SellIn,
  WearIn,
  WearOut,
} from '@api-types';
import { api, isNetworkError } from '../lib/api';
import { clientRef, todayISO } from '../lib/format';
import {
  deleteBottle,
  deleteWear,
  dropOpsForLocalBottle,
  enqueue,
  getBottles,
  getWears,
  patchBottle,
  pendingCount,
  putLocalBottle,
  putServerBottle,
  putWear,
  type LocalBottle,
  type LocalWear,
} from '../lib/offlineDb';
import { syncNow, type SyncResult } from '../lib/sync';

export type StatusFilter = 'owned' | 'wishlist' | 'tried' | 'archive' | 'all';
export type SortOption = 'date_desc' | 'alpha' | 'rating' | 'remaining' | 'last_worn';

const STATUS_GROUPS: Record<StatusFilter, CollectionStatus[] | null> = {
  owned: ['own'],
  wishlist: ['wishlist'],
  tried: ['tried'],
  archive: ['finished', 'sold', 'gifted'],
  all: null,
};

/** What the UI needs to show a bottle before the server has seen it. */
export interface FragranceDisplay {
  fragrance_name: string;
  brand_name: string;
  concentration: string;
  gender: string;
  image_url: string | null;
  families?: string[];
}

interface CollectionState {
  items: LocalBottle[];
  wears: LocalWear[];
  isLoading: boolean;
  isSyncing: boolean;
  lastError: string | null;
  offline: boolean;
  pending: number;
  statusFilter: StatusFilter;
  familyFilter: string | null;
  sortBy: SortOption;

  load: () => Promise<void>;
  sync: () => Promise<SyncResult | null>;
  add: (data: CollectionItemIn, display: FragranceDisplay) => Promise<'added' | 'queued' | 'exists'>;
  update: (b: LocalBottle, patch: CollectionItemUpdate) => Promise<void>;
  finish: (b: LocalBottle) => Promise<void>;
  sell: (b: LocalBottle, data: SellIn) => Promise<void>;
  remove: (b: LocalBottle) => Promise<void>;
  logWear: (b: LocalBottle, extra?: Partial<WearIn>) => Promise<LocalWear>;
  removeWear: (w: LocalWear) => Promise<void>;
  setStatusFilter: (f: StatusFilter) => void;
  setFamilyFilter: (f: string | null) => void;
  setSort: (s: SortOption) => void;
}

/** A bottle added offline has no server id yet: route its writes straight to the outbox. */
const notOnServerYet = <T>(): Promise<T> => Promise.reject({ isAxiosError: true, response: undefined });

function refOf(b: LocalBottle): string {
  return b.id ? String(b.id) : `ref:${b.client_ref}`;
}

export const useCollectionStore = create<CollectionState>((set, get) => {
  const reload = async () => {
    const [items, wears, pending] = await Promise.all([getBottles(), getWears(), pendingCount()]);
    set({ items, wears, pending });
  };

  /** Run an API call; on a network error fall back to `offline()` and queue. */
  const online = async <T>(call: () => Promise<T>, offline: () => Promise<void>): Promise<T | null> => {
    try {
      const out = await call();
      set({ offline: false });
      return out;
    } catch (err) {
      if (!isNetworkError(err)) throw err;
      set({ offline: true });
      await offline();
      return null;
    }
  };

  return {
    items: [],
    wears: [],
    isLoading: false,
    isSyncing: false,
    lastError: null,
    offline: false,
    pending: 0,
    statusFilter: 'owned',
    familyFilter: null,
    sortBy: 'date_desc',

    load: async () => {
      set({ isLoading: get().items.length === 0 });
      await reload();
      set({ isLoading: false });
      await get().sync();
    },

    sync: async () => {
      if (get().isSyncing) return null;
      set({ isSyncing: true });
      try {
        const res = await syncNow();
        set({ offline: res.offline, lastError: res.conflicts[0] ?? null });
        await reload();
        return res;
      } catch (err: any) {
        set({ lastError: err?.message ?? 'Sync failed' });
        return null;
      } finally {
        set({ isSyncing: false });
      }
    },

    add: async (data, display) => {
      const payload: CollectionItemIn = { ...data, client_ref: data.client_ref ?? clientRef('b') };
      try {
        const res = await online(
          () => api.post<CollectionItemOut>('/collection', payload),
          async () => {
            const now = new Date().toISOString();
            await putLocalBottle({
              id: 0, fragrance_id: payload.fragrance_id, status: payload.status ?? 'own',
              bottle_type: (payload.bottle_type ?? 'full') as BottleType, size_ml: payload.size_ml ?? null,
              purchase_price: payload.purchase_price ?? null, currency: payload.currency ?? 'EUR',
              purchase_date: payload.purchase_date ?? null, rating: payload.rating ?? null,
              remaining_pct: payload.remaining_pct ?? (payload.status === 'own' || !payload.status ? 100 : 0),
              notes: payload.notes ?? null, is_favorite: payload.is_favorite ?? false, source: payload.source ?? null,
              sold_price: null, sold_at: null, client_ref: payload.client_ref!, created_at: now, updated_at: now,
              families: display.families ?? [], wear_count: 0, last_worn_on: null, ...display,
            });
            await enqueue('bottle.add', null, payload);
          },
        );
        if (res) await putServerBottle(res.data);
        await reload();
        return res ? 'added' : 'queued';
      } catch (err: any) {
        if (err?.response?.status === 409) return 'exists';
        throw err;
      }
    },

    update: async (b, patch) => {
      set({ items: get().items.map((i) => (i.local_id === b.local_id ? { ...i, ...patch } as LocalBottle : i)) });
      const res = await online(
        () => (b.id ? api.patch<CollectionItemOut>(`/collection/${b.id}`, patch) : notOnServerYet<AxiosResponse<CollectionItemOut>>()),
        async () => {
          await patchBottle({ id: b.id, client_ref: b.client_ref }, patch as Partial<CollectionItemOut>);
          await enqueue('bottle.update', refOf(b), patch);
        },
      );
      if (res) await putServerBottle(res.data);
      await reload();
    },

    finish: async (b) => {
      const res = await online(
        () => (b.id ? api.post<CollectionItemOut>(`/collection/${b.id}/finish`) : notOnServerYet<AxiosResponse<CollectionItemOut>>()),
        async () => {
          await patchBottle({ id: b.id, client_ref: b.client_ref }, { status: 'finished', remaining_pct: 0 });
          await enqueue('bottle.finish', refOf(b));
        },
      );
      if (res) await putServerBottle(res.data);
      await reload();
    },

    sell: async (b, data) => {
      // Selling records money; keep it online-only so the numbers are right.
      const { data: out } = await api.post<CollectionItemOut>(`/collection/${b.id}/sell`, data);
      await putServerBottle(out);
      await reload();
    },

    remove: async (b) => {
      set({ items: get().items.filter((i) => i.local_id !== b.local_id) });
      if (!b.id) {
        // Never reached the server: forget it and everything queued for it.
        if (b.client_ref) await dropOpsForLocalBottle(b.client_ref);
        await deleteBottle({ client_ref: b.client_ref });
        await reload();
        return;
      }
      await online(
        () => api.delete(`/collection/${b.id}`),
        async () => enqueue('bottle.delete', refOf(b)),
      );
      await deleteBottle({ id: b.id });
      await reload();
    },

    logWear: async (b, extra = {}) => {
      const body: WearIn = { worn_on: todayISO(), client_ref: clientRef('w'), ...extra };
      const res = await online(
        () => (b.id
          ? api.post<WearOut>('/wears', { ...body, collection_item_id: b.id })
          : notOnServerYet<AxiosResponse<WearOut>>()),
        async () => {
          const now = new Date().toISOString();
          const local: WearOut = {
            id: 0, collection_item_id: b.id || null, fragrance_id: b.fragrance_id, fragrance_name: b.fragrance_name,
            brand_name: b.brand_name, worn_on: body.worn_on!, sprays: body.sprays ?? null, occasion: body.occasion ?? null,
            temp_c: body.temp_c ?? null, note: body.note ?? null, compliment: body.compliment ?? false,
            client_ref: body.client_ref!, created_at: now, remaining_pct: null,
          };
          await putWear(local, false);
          await patchBottle({ id: b.id, client_ref: b.client_ref }, {
            wear_count: b.wear_count + 1, last_worn_on: body.worn_on!,
          });
          await enqueue('wear.add', null, b.id
            ? { ...body, collection_item_id: b.id }
            : { ...body, collection_item_ref: b.client_ref });
        },
      );
      if (res) {
        await putWear(res.data, true);
        await patchBottle({ id: b.id }, {
          wear_count: b.wear_count + 1, last_worn_on: res.data.worn_on,
          ...(res.data.remaining_pct != null ? { remaining_pct: res.data.remaining_pct } : {}),
        });
      }
      await reload();
      return get().wears.find((w) => w.client_ref === body.client_ref)!;
    },

    removeWear: async (w) => {
      if (w.id) {
        await online(() => api.delete(`/wears/${w.id}`), async () => enqueue('wear.delete', String(w.id)));
      }
      await deleteWear({ id: w.id || undefined, client_ref: w.client_ref });
      await reload();
    },

    setStatusFilter: (f) => set({ statusFilter: f, familyFilter: null }),
    setFamilyFilter: (f) => set({ familyFilter: f }),
    setSort: (s) => set({ sortBy: s }),
  };
});

// ── Selectors ───────────────────────────────────────────────────────

export function filterItems(items: LocalBottle[], status: StatusFilter, family: string | null, sort: SortOption) {
  const statuses = STATUS_GROUPS[status];
  let out = items.filter((i) => !statuses || statuses.includes(i.status));
  if (family) out = out.filter((i) => i.families.includes(family));
  const byName = (a: LocalBottle, b: LocalBottle) => a.fragrance_name.localeCompare(b.fragrance_name);
  const sorters: Record<SortOption, (a: LocalBottle, b: LocalBottle) => number> = {
    date_desc: (a, b) => b.created_at.localeCompare(a.created_at),
    alpha: byName,
    rating: (a, b) => (b.rating ?? 0) - (a.rating ?? 0) || byName(a, b),
    remaining: (a, b) => a.remaining_pct - b.remaining_pct || byName(a, b),
    last_worn: (a, b) => (a.last_worn_on ?? '').localeCompare(b.last_worn_on ?? '') || byName(a, b),
  };
  return [...out].sort(sorters[sort]);
}

export function familiesOf(items: LocalBottle[]): string[] {
  return Array.from(new Set(items.flatMap((i) => i.families))).sort();
}

export function statusCounts(items: LocalBottle[]): Record<StatusFilter, number> {
  const counts = { owned: 0, wishlist: 0, tried: 0, archive: 0, all: items.length };
  for (const i of items) {
    if (i.status === 'own') counts.owned++;
    else if (i.status === 'wishlist') counts.wishlist++;
    else if (i.status === 'tried') counts.tried++;
    else counts.archive++;
  }
  return counts;
}
