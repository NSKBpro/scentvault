import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock, DollarSign, ExternalLink, Search, Trash2, X, Zap } from 'lucide-react';
import clsx from 'clsx';
import type { CountOut, FragranceListItem, Page, PriceLogIn, PriceLogOut, RetailerOut } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { useDebounce } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { Field as FormField } from '../components/ui';

// =============================================
// PRICE LOGGER PAGE
// =============================================
export default function PriceLogger() {
  const queryClient = useQueryClient();
  const fragranceSearchRef = useRef<HTMLInputElement>(null);
  const notify = useToast();
  const setToast = ({ message, type }: { message: string; type: 'success' | 'error' }) => notify(message, type);
  const [flashSuccess, setFlashSuccess] = useState(false);

  // --- Form State ---
  const [fragranceSearch, setFragranceSearch] = useState('');
  const [selectedFragrance, setSelectedFragrance] = useState<FragranceListItem | null>(null);
  const [retailerId, setRetailerId] = useState<number | ''>('');
  const [sizeMl, setSizeMl] = useState<number | ''>('');
  const [priceUsd, setPriceUsd] = useState<string>('');
  const [productUrl, setProductUrl] = useState('');
  const [isSale, setIsSale] = useState(false);
  const [showFragranceDropdown, setShowFragranceDropdown] = useState(false);

  const debouncedFragSearch = useDebounce(fragranceSearch, 150);

  // --- Lookups ---
  const { data: retailers } = useQuery({
    queryKey: ['retailers'],
    queryFn: () => api.get<RetailerOut[]>('/prices/retailers').then(r => r.data),
    staleTime: 5 * 60 * 1000
  });

  const { data: fragranceResults } = useQuery({
    queryKey: ['fragrance-search', debouncedFragSearch],
    queryFn: () => api.get<Page<FragranceListItem>>('/catalog/fragrances', { params: { search: debouncedFragSearch, size: 10 } }).then(r => r.data.items),
    enabled: debouncedFragSearch.length >= 2
  });

  const { data: todayCount, refetch: refetchCount } = useQuery({
    queryKey: ['price-log-today-count'],
    queryFn: () => api.get<CountOut>('/prices/admin/logs/today-count').then(r => r.data.count)
  });

  const { data: recentLogs, refetch: refetchRecent } = useQuery({
    queryKey: ['price-logs-recent'],
    queryFn: () => api.get<PriceLogOut[]>('/prices/admin/logs/recent', { params: { limit: 20 } }).then(r => r.data)
  });

  // --- Auto-suggest sizes from selected fragrance ---
  const availableSizes = selectedFragrance?.sizes_ml ?? [];

  // --- Submit ---
  const logMutation = useMutation({
    mutationFn: (data: PriceLogIn) => api.post<PriceLogOut>('/prices/admin/logs', data),
    onSuccess: () => {
      // Flash green
      setFlashSuccess(true);
      setTimeout(() => setFlashSuccess(false), 600);

      // Clear fragrance, price, URL — keep retailer
      setSelectedFragrance(null);
      setFragranceSearch('');
      setSizeMl('');
      setPriceUsd('');
      setProductUrl('');
      setIsSale(false);

      // Refresh sidebar
      refetchRecent();
      refetchCount();
      queryClient.invalidateQueries({ queryKey: ['price-logs-recent'] });

      // Focus back on fragrance search
      setTimeout(() => fragranceSearchRef.current?.focus(), 100);
    },
    onError: (err) => setToast({ message: errorMessage(err, 'Failed to log price'), type: 'error' })
  });

  const handleSubmit = () => {
    if (!selectedFragrance) { setToast({ message: 'Select a fragrance', type: 'error' }); return; }
    if (!retailerId) { setToast({ message: 'Select a retailer', type: 'error' }); return; }
    if (!sizeMl || Number(sizeMl) <= 0) { setToast({ message: 'Enter a valid size', type: 'error' }); return; }
    if (!priceUsd || Number(priceUsd) <= 0) { setToast({ message: 'Enter a valid price', type: 'error' }); return; }

    logMutation.mutate({
      fragrance_id: selectedFragrance.id,
      retailer_id: Number(retailerId),
      size_ml: Number(sizeMl),
      price_usd: Number(priceUsd),
      product_url: productUrl.trim() || null,
      is_sale: isSale
    });
  };

  // --- Delete recent entry ---
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/prices/admin/logs/${id}`),
    onSuccess: () => { refetchRecent(); refetchCount(); }
  });

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.fragrance-search-container')) {
        setShowFragranceDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-serif font-bold text-white">Price Logger</h1>
          <p className="text-gold/60 text-xs uppercase tracking-widest mt-1">Batch Entry Tool</p>
        </div>
        <div className="flex items-center gap-2 bg-navy-light border border-white/5 rounded-2xl px-5 py-3">
          <Zap className="w-4 h-4 text-gold" />
          <span className="text-white font-bold text-lg">{todayCount || 0}</span>
          <span className="text-gray-500 text-xs">logged today</span>
        </div>
      </div>

      {/* Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

        {/* ===== LEFT: Entry Form (60%) ===== */}
        <div className="lg:col-span-7">
          <div className={clsx(
            "bg-navy-light rounded-3xl border border-white/5 p-8 space-y-5 transition-all duration-300",
            flashSuccess && "ring-2 ring-emerald-400/40 bg-emerald-500/5"
          )}>
            <h2 className="font-serif text-lg font-bold text-white flex items-center gap-2">
              <DollarSign className="text-gold" /> Log Price
            </h2>

            {/* Fragrance Search */}
            <FormField label="Fragrance" required>
              <div className="relative fragrance-search-container">
                {selectedFragrance ? (
                  <div className="flex items-center justify-between bg-navy-dark border border-gold/30 rounded-xl p-4">
                    <div>
                      <span className="text-white font-bold">{selectedFragrance.name}</span>
                      <span className="text-gold/70 text-xs ml-2">{selectedFragrance.brand_name} · {selectedFragrance.concentration}</span>
                    </div>
                    <button
                      onClick={() => { setSelectedFragrance(null); setFragranceSearch(''); setSizeMl(''); }}
                      className="text-gray-500 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <>
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                      ref={fragranceSearchRef}
                      type="text"
                      placeholder="Search fragrance by name..."
                      value={fragranceSearch}
                      onChange={(e) => { setFragranceSearch(e.target.value); setShowFragranceDropdown(true); }}
                      onFocus={() => fragranceSearch.length >= 2 && setShowFragranceDropdown(true)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && fragranceResults?.length) {
                          e.preventDefault();
                          setSelectedFragrance(fragranceResults[0]);
                          setFragranceSearch('');
                          setShowFragranceDropdown(false);
                        }
                      }}
                      className="w-full bg-navy-dark border border-white/10 rounded-xl pl-12 pr-4 py-4 text-white outline-none focus:border-gold/40 transition-colors"
                    />
                    {showFragranceDropdown && fragranceResults && fragranceResults.length > 0 && (
                      <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-navy-dark border border-white/10 rounded-xl overflow-hidden shadow-2xl max-h-60 overflow-y-auto">
                        {fragranceResults.map((f) => (
                          <button
                            key={f.id}
                            onClick={() => {
                              setSelectedFragrance(f);
                              setFragranceSearch('');
                              setShowFragranceDropdown(false);
                            }}
                            className="w-full text-left px-4 py-3 hover:bg-gold/10 transition-colors border-b border-white/5 last:border-0"
                          >
                            <div className="text-white text-sm font-medium">{f.name}</div>
                            <div className="text-gold/70 text-xs">{f.brand_name} · {f.concentration}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </FormField>

            {/* Retailer */}
            <FormField label="Retailer" required>
              <select
                value={retailerId}
                onChange={(e) => setRetailerId(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-navy-dark border border-white/10 rounded-xl p-4 text-white outline-none focus:border-gold/40"
              >
                <option value="">Select Retailer</option>
                {(retailers || []).map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </FormField>

            {/* Size + Price row */}
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Size (ml)" required>
                <div className="space-y-2">
                  <input
                    type="number"
                    value={sizeMl}
                    onChange={(e) => setSizeMl(e.target.value ? Number(e.target.value) : '')}
                    placeholder="e.g. 100"
                    className="w-full bg-navy-dark border border-white/10 rounded-xl p-4 text-white outline-none focus:border-gold/40"
                  />
                  {availableSizes.length > 0 && (
                    <div className="flex gap-1.5">
                      {availableSizes.map((s: number) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setSizeMl(s)}
                          className={clsx(
                            "px-2 py-0.5 rounded text-[10px] font-bold transition-colors",
                            sizeMl === s
                              ? "bg-gold/20 text-gold border border-gold/30"
                              : "bg-navy-dark border border-white/5 text-gray-500 hover:text-gold"
                          )}
                        >
                          {s}ml
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </FormField>
              <FormField label="Price (USD)" required>
                <input
                  type="number"
                  step="0.01"
                  value={priceUsd}
                  onChange={(e) => setPriceUsd(e.target.value)}
                  placeholder="0.00"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSubmit(); } }}
                  className="w-full bg-navy-dark border border-white/10 rounded-xl p-4 text-white outline-none focus:border-gold/40"
                />
              </FormField>
            </div>

            {/* URL + Sale toggle */}
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <FormField label="Product URL">
                  <input
                    type="url"
                    value={productUrl}
                    onChange={(e) => setProductUrl(e.target.value)}
                    placeholder="https://retailer.com/product..."
                    className="w-full bg-navy-dark border border-white/10 rounded-xl p-4 text-white outline-none focus:border-gold/40"
                  />
                </FormField>
              </div>
              <FormField label="Sale?">
                <button
                  type="button"
                  onClick={() => setIsSale(!isSale)}
                  className={clsx(
                    "w-full p-4 rounded-xl border-2 font-bold text-sm transition-all",
                    isSale
                      ? "bg-red-500/10 border-red-400/40 text-red-400"
                      : "bg-navy-dark border-white/5 text-gray-400 hover:border-white/10"
                  )}
                >
                  {isSale ? '🔥 ON SALE' : 'Regular'}
                </button>
              </FormField>
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={logMutation.isPending}
              className="w-full bg-gold text-navy py-4 rounded-2xl font-bold text-sm hover:bg-gold-light transition-all shadow-lg shadow-gold/20 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <DollarSign className="w-5 h-5" />
              {logMutation.isPending ? 'Logging...' : 'Log Price & Next'}
            </button>
          </div>
        </div>

        {/* ===== RIGHT: Recent Entries Sidebar (40%) ===== */}
        <div className="lg:col-span-5">
          <div className="bg-navy-light rounded-3xl border border-white/5 overflow-hidden">
            <div className="p-5 border-b border-white/5 flex items-center justify-between">
              <h3 className="font-serif font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-gold" /> Recent entries
              </h3>
              <span className="text-gold text-xs font-bold">{recentLogs?.length || 0} entries</span>
            </div>

            <div className="max-h-[600px] overflow-y-auto divide-y divide-white/5">
              {(!recentLogs || recentLogs.length === 0) && (
                <div className="p-8 text-center text-gray-400 text-sm">No prices logged yet</div>
              )}
              {(recentLogs || []).map((log) => (
                <div key={log.id} className="group p-4 hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-white text-sm font-medium truncate">{log.fragrance?.name}</span>
                        {log.is_sale && <span className="text-red-400 text-[9px] font-bold px-1.5 py-0.5 bg-red-400/10 rounded">SALE</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-gold/70 text-[11px]">{log.fragrance.brand_name}</span>
                        <span className="text-gray-400 text-[10px]">·</span>
                        <span className="text-gray-500 text-[10px]">{log.retailer?.name}</span>
                        <span className="text-gray-400 text-[10px]">·</span>
                        <span className="text-gray-500 text-[10px]">{log.size_ml}ml</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-white font-bold text-sm">${log.price_usd.toFixed(2)}</span>
                      {log.product_url && (
                        <a href={log.product_url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-gold" aria-label="Open product page">
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                      <button
                        onClick={() => confirm('Delete this entry?') && deleteMutation.mutate(log.id)}
                        className="text-red-300 opacity-40 group-hover:opacity-100 transition-opacity"
                        aria-label="Delete entry"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="text-gray-400 text-[9px] mt-1.5">
                    {new Date(log.logged_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}