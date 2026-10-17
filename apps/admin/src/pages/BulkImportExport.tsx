import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Download, FileUp, Upload } from 'lucide-react';
import clsx from 'clsx';
import type { ImportConfirmOut, ImportPreviewOut } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { useToast } from '../lib/toast';
import { Badge, Button, Card, PageHeader } from '../components/ui';

const EXPORT_TABLES = [
  'brands', 'notes', 'families', 'accords', 'occasions', 'retailers', 'fragrances', 'fragrance_notes',
  'fragrance_families', 'fragrance_accords', 'fragrance_prices', 'price_logs',
];

const TEMPLATE =
  'name,brand_name,concentration,gender,top_notes,heart_notes,base_notes,families,accords,description,release_year,longevity_hours,sillage,season_spring,season_summer,season_fall,season_winter,image_url,prices\n' +
  'Example Scent,Example House,EDP,Unisex,Bergamot;Pink Pepper,Iris;Rose,Vanilla;Sandalwood,Floral;Woody,Powdery;Woody,Optional text,2024,8,Moderate,yes,,yes,yes,,50:95;100:140\n';

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ExportCard() {
  const toast = useToast();
  const [selected, setSelected] = useState(new Set(EXPORT_TABLES));
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const exp = useMutation({
    mutationFn: async () => {
      const res = await api.get('/admin/export', { params: { format, tables: Array.from(selected).join(',') }, responseType: 'blob' });
      const name = /filename="?([^"]+)"?/.exec(res.headers['content-disposition'] ?? '')?.[1] ?? 'scentvault_export.zip';
      download(res.data as Blob, name);
    },
    onError: (e) => toast(errorMessage(e, 'Export failed'), 'error'),
  });
  const toggle = (t: string) => {
    const next = new Set(selected);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    setSelected(next);
  };
  return (
    <Card>
      <h2 className="font-serif text-lg text-white flex items-center gap-2">
        <Download className="w-5 h-5 text-gold" /> Export
      </h2>
      <p className="text-sm text-gray-400 mt-1">A ZIP with one file per table (plus an import template). Use it for backups or to move the catalog.</p>
      <div className="flex items-center justify-between mt-4 mb-2">
        <span className="text-xs font-bold text-gold uppercase tracking-wider">Tables</span>
        <button className="text-xs text-gray-300 hover:text-gold" onClick={() => setSelected(selected.size === EXPORT_TABLES.length ? new Set() : new Set(EXPORT_TABLES))}>
          {selected.size === EXPORT_TABLES.length ? 'Select none' : 'Select all'}
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {EXPORT_TABLES.map((t) => (
          <label key={t} className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border text-sm cursor-pointer', selected.has(t) ? 'border-gold/40 bg-gold/10 text-gold' : 'border-white/10 text-gray-300')}>
            <input type="checkbox" checked={selected.has(t)} onChange={() => toggle(t)} className="accent-[#c9a96e]" /> {t}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-3 mt-5">
        <div role="radiogroup" aria-label="Format" className="flex bg-navy-dark rounded-lg p-1 border border-white/10">
          {(['csv', 'json'] as const).map((f) => (
            <button key={f} role="radio" aria-checked={format === f} onClick={() => setFormat(f)} className={clsx('px-3 py-1.5 rounded-md text-sm font-bold uppercase', format === f ? 'bg-gold text-navy' : 'text-gray-300')}>
              {f}
            </button>
          ))}
        </div>
        <Button onClick={() => exp.mutate()} loading={exp.isPending} disabled={selected.size === 0}>
          Download ZIP
        </Button>
      </div>
    </Card>
  );
}

function ImportCard() {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewOut | null>(null);
  const [result, setResult] = useState<ImportConfirmOut | null>(null);
  const [skipErrors, setSkipErrors] = useState(true);
  const [filter, setFilter] = useState<'all' | 'ok' | 'warning' | 'error'>('all');

  const doPreview = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append('file', file!);
      return (await api.post<ImportPreviewOut>('/admin/import/preview', fd)).data;
    },
    onSuccess: (p) => {
      setPreview(p);
      setResult(null);
    },
    onError: (e) => toast(errorMessage(e, 'Preview failed'), 'error'),
  });
  const confirmImport = useMutation({
    mutationFn: async () => (await api.post<ImportConfirmOut>('/admin/import/confirm', { session_data: preview!.session_data, skip_errors: skipErrors })).data,
    onSuccess: (r) => {
      setResult(r);
      setPreview(null);
      toast(`Imported ${r.inserted} fragrance(s); embeddings queued`);
    },
    onError: (e) => toast(errorMessage(e, 'Import failed'), 'error'),
  });

  const rows = preview?.rows.filter((r) => filter === 'all' || r.status === filter) ?? [];
  const importable = preview ? preview.valid_rows + preview.warning_rows : 0;

  return (
    <Card>
      <h2 className="font-serif text-lg text-white flex items-center gap-2">
        <Upload className="w-5 h-5 text-gold" /> Import fragrances
      </h2>
      <p className="text-sm text-gray-400 mt-1">
        Upload a CSV, check the preview, then confirm. Lists use <code className="text-gold">;</code>, prices use <code className="text-gold">size:price</code> pairs. Missing brands, notes, families and accords are created.
      </p>
      <div className="flex flex-wrap items-center gap-3 mt-4">
        <Button variant="secondary" onClick={() => download(new Blob([TEMPLATE], { type: 'text/csv' }), 'scentvault_import_template.csv')}>
          <Download className="w-4 h-4" /> Template
        </Button>
        <label className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-white/20 text-sm text-gray-200 cursor-pointer hover:border-gold/40">
          <FileUp className="w-4 h-4 text-gold" />
          {file ? file.name : 'Choose CSV…'}
          <input type="file" accept=".csv" className="sr-only" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); setResult(null); }} />
        </label>
        <Button onClick={() => doPreview.mutate()} disabled={!file} loading={doPreview.isPending}>
          Preview
        </Button>
      </div>

      {preview && (
        <div className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-2">
            {([['all', `All ${preview.total_rows}`], ['ok', `OK ${preview.valid_rows}`], ['warning', `Warnings ${preview.warning_rows}`], ['error', `Errors ${preview.error_rows}`]] as const).map(([k, label]) => (
              <button key={k} onClick={() => setFilter(k)} className={clsx('px-3 py-1.5 rounded-full text-xs font-bold border', filter === k ? 'bg-gold text-navy border-gold' : 'border-white/15 text-gray-300')}>
                {label}
              </button>
            ))}
          </div>
          <div className="max-h-[420px] overflow-auto rounded-xl border border-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead className="bg-navy-dark sticky top-0">
                <tr className="text-left text-[11px] text-gold uppercase tracking-wider">
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Fragrance</th>
                  <th className="px-3 py-2">Messages</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {rows.map((r) => (
                  <tr key={r.row_number}>
                    <td className="px-3 py-2 text-gray-400">{r.row_number}</td>
                    <td className="px-3 py-2">
                      <Badge tone={r.status === 'ok' ? 'green' : r.status === 'warning' ? 'gold' : 'red'}>{r.status}</Badge>
                    </td>
                    <td className="px-3 py-2 text-white">
                      {String(r.data.brand_name ?? '')} — {String(r.data.name ?? '')} <span className="text-gray-400">{String(r.data.concentration ?? '')}</span>
                    </td>
                    <td className="px-3 py-2 text-gray-300 whitespace-normal">{r.messages.join(' · ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-200">
              <input type="checkbox" checked={skipErrors} onChange={(e) => setSkipErrors(e.target.checked)} className="accent-[#c9a96e]" /> Skip rows that fail (others still import)
            </label>
            <Button onClick={() => confirmImport.mutate()} loading={confirmImport.isPending} disabled={importable === 0}>
              Import {importable} row{importable === 1 ? '' : 's'}
            </Button>
          </div>
        </div>
      )}

      {result && (
        <div className="mt-6 p-4 rounded-xl bg-navy-dark border border-white/[0.08] text-sm space-y-1">
          <div className="text-emerald-300">Inserted: {result.inserted}</div>
          <div className="text-amber-200">Skipped: {result.skipped}</div>
          <div className="text-gray-300">Embeddings queued: {result.embeddings_queued}</div>
          {result.errors.length > 0 && <div className="text-red-300 pt-2">{result.errors.join(' · ')}</div>}
        </div>
      )}
    </Card>
  );
}

export default function BulkImportExport() {
  return (
    <div className="space-y-6">
      <PageHeader title="Import / export" subtitle="Move catalog data in and out" />
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-6 items-start">
        <ImportCard />
        <ExportCard />
      </div>
    </div>
  );
}
