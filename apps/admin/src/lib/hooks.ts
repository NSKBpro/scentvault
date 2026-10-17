import { useEffect, useState } from 'react';

export function useDebounce<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export const usd = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`);
export const shortDate = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString() : '—');
