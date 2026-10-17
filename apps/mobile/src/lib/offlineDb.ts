/**
 * Local SQLite cache + outbox (offline-first).
 *
 * - `bottles` caches the collection as JSON rows keyed by server id and/or client_ref.
 * - `wears` caches recent wear-log entries the same way.
 * - `outbox` holds writes made while offline; `sync.ts` replays them in order.
 *
 * Rows with `synced = 0` were created on this device and are never deleted by a
 * refresh from the server (that was the old data-loss bug).
 */
import * as SQLite from 'expo-sqlite';
import type { CollectionItemOut, WearOut } from '@api-types';

const SCHEMA_VERSION = 2;
let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

export function getDB(): Promise<SQLite.SQLiteDatabase> {
  dbPromise ??= (async () => {
    const db = await SQLite.openDatabaseAsync('scentvault.db');
    await migrate(db);
    return db;
  })();
  return dbPromise;
}

async function migrate(db: SQLite.SQLiteDatabase) {
  const row = await db.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  const v = row?.user_version ?? 0;
  if (v >= SCHEMA_VERSION) return;
  // v1 stored a flat table that was wiped on every refresh; start clean.
  await db.execAsync(`
    DROP TABLE IF EXISTS collection;
    DROP TABLE IF EXISTS sync_queue;
    CREATE TABLE IF NOT EXISTS bottles (
      local_id   INTEGER PRIMARY KEY AUTOINCREMENT,
      server_id  INTEGER UNIQUE,
      client_ref TEXT UNIQUE,
      data       TEXT NOT NULL,
      synced     INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS wears (
      local_id   INTEGER PRIMARY KEY AUTOINCREMENT,
      server_id  INTEGER UNIQUE,
      client_ref TEXT UNIQUE,
      data       TEXT NOT NULL,
      synced     INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS outbox (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      kind       TEXT NOT NULL,
      ref        TEXT,
      payload    TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    PRAGMA user_version = ${SCHEMA_VERSION};
  `);
}

// ── Bottles ─────────────────────────────────────────────────────────

/** A cached bottle. `id` is the server id (0 until an offline add syncs). */
export type LocalBottle = CollectionItemOut & { local_id: number; synced: 0 | 1 };

type Row = { local_id: number; server_id: number | null; client_ref: string | null; data: string; synced: number };

function toBottle(r: Row): LocalBottle {
  const d = JSON.parse(r.data) as CollectionItemOut;
  return { ...d, id: r.server_id ?? 0, client_ref: r.client_ref ?? d.client_ref, local_id: r.local_id, synced: r.synced ? 1 : 0 };
}

export async function getBottles(): Promise<LocalBottle[]> {
  const db = await getDB();
  const rows = await db.getAllAsync<Row>('SELECT * FROM bottles ORDER BY local_id DESC');
  return rows.map(toBottle);
}

export async function putServerBottle(item: CollectionItemOut): Promise<void> {
  const db = await getDB();
  // Match by server id, or by client_ref when this is the server's echo of an offline add.
  const existing = await db.getFirstAsync<Row>(
    'SELECT * FROM bottles WHERE server_id = ? OR (client_ref IS NOT NULL AND client_ref = ?)',
    [item.id, item.client_ref ?? '__none__'],
  );
  const json = JSON.stringify(item);
  if (existing) {
    await db.runAsync('UPDATE bottles SET server_id = ?, client_ref = ?, data = ?, synced = 1 WHERE local_id = ?', [
      item.id, item.client_ref ?? existing.client_ref, json, existing.local_id,
    ]);
  } else {
    await db.runAsync('INSERT INTO bottles (server_id, client_ref, data, synced) VALUES (?, ?, ?, 1)', [
      item.id, item.client_ref ?? null, json,
    ]);
  }
}

export async function putLocalBottle(item: CollectionItemOut & { client_ref: string }): Promise<void> {
  const db = await getDB();
  await db.runAsync('INSERT OR REPLACE INTO bottles (server_id, client_ref, data, synced) VALUES (NULL, ?, ?, 0)', [
    item.client_ref, JSON.stringify(item),
  ]);
}

/** Apply a partial change to a cached bottle (by server id or client_ref). */
export async function patchBottle(key: { id?: number; client_ref?: string | null }, patch: Partial<CollectionItemOut>) {
  const db = await getDB();
  const row = await findBottleRow(key);
  if (!row) return;
  const merged = { ...(JSON.parse(row.data) as CollectionItemOut), ...patch };
  await db.runAsync('UPDATE bottles SET data = ? WHERE local_id = ?', [JSON.stringify(merged), row.local_id]);
}

export async function deleteBottle(key: { id?: number; client_ref?: string | null }) {
  const db = await getDB();
  const row = await findBottleRow(key);
  if (row) await db.runAsync('DELETE FROM bottles WHERE local_id = ?', [row.local_id]);
}

export async function findBottleRow(key: { id?: number; client_ref?: string | null }): Promise<Row | null> {
  const db = await getDB();
  if (key.id) {
    const r = await db.getFirstAsync<Row>('SELECT * FROM bottles WHERE server_id = ?', [key.id]);
    if (r) return r;
  }
  if (key.client_ref) return db.getFirstAsync<Row>('SELECT * FROM bottles WHERE client_ref = ?', [key.client_ref]);
  return null;
}

/** Replace the synced part of the cache with the server's list; pending local rows survive. */
export async function mergeServerBottles(items: CollectionItemOut[]): Promise<void> {
  const db = await getDB();
  for (const it of items) await putServerBottle(it);
  const keep = items.map((i) => i.id);
  if (keep.length) {
    await db.runAsync(
      `DELETE FROM bottles WHERE synced = 1 AND server_id IS NOT NULL AND server_id NOT IN (${keep.map(() => '?').join(',')})`,
      keep,
    );
  } else {
    await db.runAsync('DELETE FROM bottles WHERE synced = 1');
  }
}

// ── Wears ───────────────────────────────────────────────────────────

export type LocalWear = WearOut & { local_id: number; synced: 0 | 1 };

export async function getWears(): Promise<LocalWear[]> {
  const db = await getDB();
  const rows = await db.getAllAsync<Row>('SELECT * FROM wears');
  return rows
    .map((r) => ({ ...(JSON.parse(r.data) as WearOut), id: r.server_id ?? 0, local_id: r.local_id, synced: (r.synced ? 1 : 0) as 0 | 1 }))
    .sort((a, b) => b.worn_on.localeCompare(a.worn_on) || b.created_at.localeCompare(a.created_at));
}

export async function putWear(w: WearOut, synced: boolean): Promise<void> {
  const db = await getDB();
  const existing = await db.getFirstAsync<Row>(
    'SELECT * FROM wears WHERE (server_id IS NOT NULL AND server_id = ?) OR (client_ref IS NOT NULL AND client_ref = ?)',
    [w.id || -1, w.client_ref ?? '__none__'],
  );
  if (existing) {
    await db.runAsync('UPDATE wears SET server_id = ?, data = ?, synced = ? WHERE local_id = ?', [
      w.id || null, JSON.stringify(w), synced ? 1 : 0, existing.local_id,
    ]);
  } else {
    await db.runAsync('INSERT INTO wears (server_id, client_ref, data, synced) VALUES (?, ?, ?, ?)', [
      w.id || null, w.client_ref ?? null, JSON.stringify(w), synced ? 1 : 0,
    ]);
  }
}

export async function deleteWear(key: { id?: number; client_ref?: string | null }) {
  const db = await getDB();
  if (key.id) await db.runAsync('DELETE FROM wears WHERE server_id = ?', [key.id]);
  else if (key.client_ref) await db.runAsync('DELETE FROM wears WHERE client_ref = ?', [key.client_ref]);
}

export async function mergeServerWears(items: WearOut[], sinceISO: string): Promise<void> {
  const db = await getDB();
  for (const w of items) await putWear(w, true);
  const keep = items.map((w) => w.id);
  const rows = await db.getAllAsync<Row>('SELECT * FROM wears WHERE synced = 1');
  for (const r of rows) {
    const w = JSON.parse(r.data) as WearOut;
    if (w.worn_on >= sinceISO && r.server_id && !keep.includes(r.server_id)) {
      await db.runAsync('DELETE FROM wears WHERE local_id = ?', [r.local_id]);
    }
  }
}

// ── Outbox ──────────────────────────────────────────────────────────

export type OutboxKind =
  | 'bottle.add'
  | 'bottle.update'
  | 'bottle.finish'
  | 'bottle.delete'
  | 'wear.add'
  | 'wear.delete';

export interface OutboxItem {
  id: number;
  kind: OutboxKind;
  /** Server id as text, or "ref:<client_ref>" for rows created offline. */
  ref: string | null;
  payload: string;
}

export async function enqueue(kind: OutboxKind, ref: string | null, payload: unknown = {}): Promise<void> {
  const db = await getDB();
  await db.runAsync('INSERT INTO outbox (kind, ref, payload) VALUES (?, ?, ?)', [kind, ref, JSON.stringify(payload)]);
}

export async function pendingOps(): Promise<OutboxItem[]> {
  const db = await getDB();
  return db.getAllAsync<OutboxItem>('SELECT id, kind, ref, payload FROM outbox ORDER BY id ASC');
}

export async function pendingCount(): Promise<number> {
  const db = await getDB();
  const r = await db.getFirstAsync<{ n: number }>('SELECT COUNT(*) AS n FROM outbox');
  return r?.n ?? 0;
}

export async function removeOp(id: number): Promise<void> {
  const db = await getDB();
  await db.runAsync('DELETE FROM outbox WHERE id = ?', [id]);
}

/** Forget everything queued for a bottle that never reached the server. */
export async function dropOpsForLocalBottle(clientRef: string): Promise<void> {
  const db = await getDB();
  const needle = `%"client_ref":"${clientRef}"%`;
  await db.runAsync(
    `DELETE FROM outbox WHERE ref = ? OR (kind = 'bottle.add' AND payload LIKE ?)
       OR (kind = 'wear.add' AND payload LIKE ?)`,
    [`ref:${clientRef}`, needle, `%"collection_item_ref":"${clientRef}"%`],
  );
}

export async function clearAll(): Promise<void> {
  const db = await getDB();
  await db.execAsync('DELETE FROM bottles; DELETE FROM wears; DELETE FROM outbox;');
}
