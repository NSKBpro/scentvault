import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Filter, Trash2 } from 'lucide-react';
import type { FragranceListItem, Page, PriceLogOut, RetailerOut } from '@api-types';
import api, { errorMessage } from '../lib/api';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Badge, Card, PageHeader, inputClass } from '../components/ui';

function InlinePrice({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(String(value));
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (editing) ref.current?.focus();
  }, [editing]);
  const commit = () => {
    const n = Number(text);
    if (!Number.isNaN(n) && n > 0 && n !== value) onSave(n);
    setEditing(false);
  };
  if (editing)
    return (
      <input
        ref={ref}
        type="number"
        step="0.01"
        value={text}
        aria-label="Price"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => (e.key === 'Enter' ? commit() : e.key === 'Escape' && setEditing(false))}
        onBlur={commit}
        className="w-24 bg-navy-dark border border-gold/40 rounded px-2 py-1 text-white text-sm outline-none"
      />
    );
  return (
    <button onClick={() => { setText(String(value)); setEditing(true); }} className="text-white font-medium hover:text-gold cursor-text" title="Click to edit">
      ${value.toFixed(2)}
    </button>
  );
}

export default function PriceHistory() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [fragranceId, setFragranceId] = useState('');
  const [retailerId, setRetailerId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sale, setSale] = useState('');

  const { data: retailers } = useQuery({ queryKey: ['retailers'], queryFn: () => api.get<RetailerOut[]>('/prices/retailers').then((r) => r.data) });
  const { data: fragrances } = useQuery({
    queryKey: ['fragrances', 'picker'],
    queryFn: () => api.get<Page<FragranceListItem>>('/catalog/fragrances', { params: { size: 500, sort: 'brand' } }).then((r) => r.data.items),
  });
  const { data, isLoading } = useQuery({
    queryKey: ['price-logs', page, fragranceId, retailerId, dateFrom, dateTo, sale],
    queryFn: () =>
      api
        .get<Page<PriceLogOut>>('/prices/admin/logs', {
          params: {
            page,
            size: 20,
            fragrance_id: fragranceId || undefined,
            retailer_id: retailerId || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            is_sale: sale === '' ? undefined : sale === 'true',
          },
        })
        .then((r) => r.data),
    placeholderData: (p) => p,
  });

  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/prices/admin/logs/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['price-logs'] });
      toast('Entry deleted');
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });
  const update = useMutation({
    mutationFn: ({ id, price }: { id: number; price: number }) => api.put(`/prices/admin/logs/${id}`, { price_usd: price }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['price-logs'] });
      toast('Price updated');
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const set = (fn: (v: string) => void) => (v: string) => {
    fn(v);
    setPage(1);
  };
  const hasFilters = fragranceId || retailerId || dateFrom || dateTo || sale;

  const columns: Column<PriceLogOut>[] = [
    {
      header: 'Fragrance',
      cell: (r) => (
        <div>
          <div className="text-white text-sm font-medium">{r.fragrance.name}</div>
          <div className="text-gold/70 text-[11px]">{r.fragrance.brand_name}</div>
        </div>
      ),
    },
    { header: 'Retailer', cell: (r) => r.retailer.name },
    { header: 'Size', cell: (r) => `${r.size_ml} ml` },
    { header: 'Price', cell: (r) => <InlinePrice value={r.price_usd} onSave={(v) => update.mutate({ id: r.id, price: v })} /> },
    { header: 'Per ml', cell: (r) => <span className="text-gray-400">${(r.price_usd / r.size_ml).toFixed(2)}</span> },
    { header: 'Sale', cell: (r) => (r.is_sale ? <Badge tone="red">sale</Badge> : <span className="text-gray-500">—</span>) },
    {
      header: 'Link',
      cell: (r) =>
        r.product_url ? (
          <a href={r.product_url} target="_blank" rel="noopener noreferrer" className="text-gold/70 hover:text-gold" aria-label="Open product page">
            <ExternalLink className="w-4 h-4" />
          </a>
        ) : (
          <span className="text-gray-500">—</span>
        ),
    },
    { header: 'Logged', cell: (r) => <span className="text-gray-400 text-xs">{new Date(r.logged_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span> },
    {
      header: '',
      cell: (r) => (
        <button onClick={() => confirm('Delete this entry?') && del.mutate(r.id)} className="p-1.5 text-red-300 hover:bg-red-400/10 rounded" aria-label="Delete entry">
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Price history" subtitle={`${data?.total ?? 0} logged prices`} />
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-gold" />
          <span className="text-white text-sm font-bold">Filters</span>
          {hasFilters && (
            <button
              onClick={() => {
                setFragranceId('');
                setRetailerId('');
                setDateFrom('');
                setDateTo('');
                setSale('');
                setPage(1);
              }}
              className="ml-auto text-xs text-gray-400 hover:text-gold"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <select aria-label="Fragrance" className={inputClass} value={fragranceId} onChange={(e) => set(setFragranceId)(e.target.value)}>
            <option value="">All fragrances</option>
            {fragrances?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.brand_name} — {f.name}
              </option>
            ))}
          </select>
          <select aria-label="Retailer" className={inputClass} value={retailerId} onChange={(e) => set(setRetailerId)(e.target.value)}>
            <option value="">All retailers</option>
            {retailers?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <input type="date" aria-label="From" className={inputClass} value={dateFrom} onChange={(e) => set(setDateFrom)(e.target.value)} />
          <input type="date" aria-label="To" className={inputClass} value={dateTo} onChange={(e) => set(setDateTo)(e.target.value)} />
          <select aria-label="Sale" className={inputClass} value={sale} onChange={(e) => set(setSale)(e.target.value)}>
            <option value="">Sale and regular</option>
            <option value="true">Sale only</option>
            <option value="false">Regular only</option>
          </select>
        </div>
      </Card>
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(r) => r.id} isLoading={isLoading} page={page} total={data?.total ?? 0} size={20} onPage={setPage} />
    </div>
  );
}
