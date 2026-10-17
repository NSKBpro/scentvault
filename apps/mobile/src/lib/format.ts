/** Display helpers: money, dates, labels. */

const SYMBOLS: Record<string, string> = { EUR: '€', USD: '$', GBP: '£', RSD: 'RSD ' };

export function money(amount: number | null | undefined, currency = 'EUR', digits?: number): string {
  if (amount == null || Number.isNaN(amount)) return '—';
  const d = digits ?? (currency === 'RSD' || Math.abs(amount) >= 100 ? 0 : 2);
  const n = amount.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const sym = SYMBOLS[currency] ?? `${currency} `;
  return sym.endsWith(' ') ? `${n} ${sym.trim()}` : `${sym}${n}`;
}

/** Convert a USD catalog price with the rates from /meta. */
export function fromUsd(usd: number | null | undefined, currency: string, rates: Record<string, number>): number | null {
  if (usd == null) return null;
  return usd * (rates[currency] ?? 1);
}

export function todayISO(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function relativeDays(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const then = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).getTime();
  const days = Math.round((Date.now() - then) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  return `${Math.round(days / 30)} months ago`;
}

export const STATUS_LABEL: Record<string, string> = {
  own: 'Owned',
  wishlist: 'Wishlist',
  tried: 'Tried',
  finished: 'Finished',
  sold: 'Sold',
  gifted: 'Gifted',
};

export const BOTTLE_LABEL: Record<string, string> = {
  full: 'Full bottle',
  decant: 'Decant',
  sample: 'Sample',
  tester: 'Tester',
};

export function bottleBadge(type: string, sizeMl: number | null): string | null {
  if (type === 'full') return null;
  return sizeMl ? `${BOTTLE_LABEL[type]} ${sizeMl} ml` : BOTTLE_LABEL[type];
}

/** Random-enough id for offline idempotency (client_ref). */
export function clientRef(prefix = 'm'): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
