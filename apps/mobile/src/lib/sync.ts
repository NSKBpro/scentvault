/**
 * Offline sync protocol.
 *
 * 1. Replay the outbox in order. Adds carry a `client_ref`, so replaying an add the
 *    server already has returns the original row instead of a duplicate.
 * 2. Only then pull the server state and merge it into the cache (never deleting
 *    rows that are still waiting to sync).
 *
 * A network failure stops the replay and leaves the remaining ops queued.
 */
import type { CollectionItemOut, WearOut } from '@api-types';
import { api, isNetworkError } from './api';
import {
  findBottleRow,
  mergeServerBottles,
  mergeServerWears,
  pendingOps,
  putServerBottle,
  putWear,
  removeOp,
  deleteBottle,
  type OutboxItem,
} from './offlineDb';

export interface SyncResult {
  synced: number;
  failed: number;
  conflicts: string[];
  offline: boolean;
}

const WEAR_WINDOW_DAYS = 120;

async function resolveBottleId(ref: string | null): Promise<number | null> {
  if (!ref) return null;
  if (!ref.startsWith('ref:')) return Number(ref);
  const row = await findBottleRow({ client_ref: ref.slice(4) });
  return row?.server_id ?? null;
}

async function replay(op: OutboxItem): Promise<'done' | 'retry'> {
  const payload = JSON.parse(op.payload || '{}');
  switch (op.kind) {
    case 'bottle.add': {
      const { data } = await api.post<CollectionItemOut>('/collection', payload);
      await putServerBottle(data);
      return 'done';
    }
    case 'bottle.update':
    case 'bottle.finish':
    case 'bottle.delete': {
      const id = await resolveBottleId(op.ref);
      if (!id) return 'retry'; // its add hasn't synced yet
      if (op.kind === 'bottle.delete') {
        await api.delete(`/collection/${id}`);
        return 'done';
      }
      const { data } = op.kind === 'bottle.finish'
        ? await api.post<CollectionItemOut>(`/collection/${id}/finish`)
        : await api.patch<CollectionItemOut>(`/collection/${id}`, payload);
      await putServerBottle(data);
      return 'done';
    }
    case 'wear.add': {
      if (payload.collection_item_ref) {
        const id = await resolveBottleId(`ref:${payload.collection_item_ref}`);
        if (!id) return 'retry';
        payload.collection_item_id = id;
        delete payload.collection_item_ref;
      }
      const { data } = await api.post<WearOut>('/wears', payload);
      await putWear(data, true);
      return 'done';
    }
    case 'wear.delete': {
      if (op.ref) await api.delete(`/wears/${op.ref}`);
      return 'done';
    }
  }
}

export async function syncNow(): Promise<SyncResult> {
  const result: SyncResult = { synced: 0, failed: 0, conflicts: [], offline: false };
  for (const op of await pendingOps()) {
    try {
      const outcome = await replay(op);
      if (outcome === 'done') {
        await removeOp(op.id);
        result.synced++;
      }
    } catch (err: any) {
      if (isNetworkError(err)) {
        result.offline = true;
        break;
      }
      const status = err?.response?.status;
      if (status === 409 || status === 404 || status === 422) {
        // The server disagrees (already exists / gone / invalid): server wins, drop the op.
        result.conflicts.push(`${op.kind}: ${err?.response?.data?.detail ?? status}`);
        if (op.kind === 'bottle.add' && status === 409) {
          await deleteBottle({ client_ref: JSON.parse(op.payload).client_ref });
        }
        await removeOp(op.id);
      } else {
        result.failed++;
      }
    }
  }
  if (!result.offline) {
    try {
      await pull();
    } catch (err) {
      if (isNetworkError(err)) result.offline = true;
      else throw err;
    }
  }
  return result;
}

export async function pull(): Promise<void> {
  const since = new Date(Date.now() - WEAR_WINDOW_DAYS * 86_400_000).toISOString().slice(0, 10);
  const [bottles, wears] = await Promise.all([
    api.get<CollectionItemOut[]>('/collection'),
    api.get<WearOut[]>('/wears', { params: { from: since } }),
  ]);
  await mergeServerBottles(bottles.data);
  await mergeServerWears(wears.data, since);
}
