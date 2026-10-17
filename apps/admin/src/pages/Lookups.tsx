/**
 * Brands, notes, families, accords and occasions share one page component,
 * configured per kind. Counts link to the fragrance list filtered by that item.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { Edit2, Plus, Search, Trash2, Upload } from 'lucide-react';
import type { NoteImportResult, Page } from '@api-types';
import { RADAR_AXES } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { useDebounce } from '../lib/hooks';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Badge, Button, Field, Modal, PageHeader, inputClass } from '../components/ui';

type Row = { id: number; name: string; fragrance_count?: number } & Record<string, unknown>;

interface FieldDef {
  key: string;
  label: string;
  type?: 'text' | 'textarea' | 'url' | 'select';
  options?: readonly string[];
  required?: boolean;
  hint?: string;
}

interface KindConfig {
  kind: 'brands' | 'notes' | 'families' | 'accords' | 'occasions';
  title: string;
  subtitle: string;
  singular: string;
  filterParam?: string;
  fields: FieldDef[];
  extraColumns?: Column<Row>[];
}

const PAGE_SIZE = 20;

function LookupPage({ config }: { config: KindConfig }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Row | 'new' | null>(null);
  const [importing, setImporting] = useState(false);
  const debounced = useDebounce(search);

  const { data, isLoading } = useQuery({
    queryKey: [config.kind, page, debounced, category],
    queryFn: () =>
      api
        .get<Page<Row>>(`/catalog/${config.kind}`, {
          params: { page, size: PAGE_SIZE, search: debounced || undefined, category: category || undefined },
        })
        .then((r) => r.data),
  });

  const { data: categories } = useQuery({
    queryKey: ['note-categories'],
    queryFn: () => api.get<string[]>('/catalog/notes/categories').then((r) => r.data),
    enabled: config.kind === 'notes',
  });

  const save = useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id ? api.put(`/catalog/admin/${config.kind}/${id}`, body) : api.post(`/catalog/admin/${config.kind}`, body),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: [config.kind] });
      qc.invalidateQueries({ queryKey: ['lookups'] });
      toast(`${config.singular} ${vars.id ? 'updated' : 'created'}`);
      setEditing(null);
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/catalog/admin/${config.kind}/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [config.kind] });
      toast(`${config.singular} deleted`);
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const columns: Column<Row>[] = [
    { header: 'Name', cell: (r) => <span className="font-semibold text-white">{r.name}</span> },
    ...(config.extraColumns ?? []),
  ];
  if (config.filterParam) {
    columns.push({
      header: 'Fragrances',
      cell: (r) =>
        r.fragrance_count ? (
          <Link to={`/fragrances?${config.filterParam}=${r.id}`} className="text-gold hover:underline">
            {r.fragrance_count}
          </Link>
        ) : (
          <span className="text-gray-500">0</span>
        ),
    });
  }
  columns.push({
    header: 'Actions',
    cell: (r) => (
      <div className="flex gap-1">
        <button onClick={() => setEditing(r)} className="p-1.5 text-gold hover:bg-gold/10 rounded" aria-label={`Edit ${r.name}`}>
          <Edit2 className="w-4 h-4" />
        </button>
        <button
          onClick={() => {
            const warn = r.fragrance_count ? ` It is used by ${r.fragrance_count} fragrance(s), which will lose it.` : '';
            if (confirm(`Delete “${r.name}”?${warn}`)) remove.mutate(r.id);
          }}
          className="p-1.5 text-red-300 hover:bg-red-400/10 rounded"
          aria-label={`Delete ${r.name}`}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    ),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={config.title}
        subtitle={config.subtitle}
        actions={
          <>
            {config.kind === 'notes' && (
              <Button variant="secondary" onClick={() => setImporting(true)}>
                <Upload className="w-4 h-4" /> Import CSV
              </Button>
            )}
            <Button onClick={() => setEditing('new')}>
              <Plus className="w-4 h-4" /> New {config.singular.toLowerCase()}
            </Button>
          </>
        }
      />
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className={`${inputClass} pl-11`}
            placeholder={`Search ${config.title.toLowerCase()}…`}
            aria-label="Search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        {config.kind === 'notes' && (
          <select
            className={`${inputClass} w-52`}
            aria-label="Category"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {categories?.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(r) => r.id}
        isLoading={isLoading}
        page={page}
        total={data?.total ?? 0}
        size={PAGE_SIZE}
        onPage={setPage}
      />
      {editing && (
        <EditModal
          config={config}
          row={editing === 'new' ? null : editing}
          categories={categories ?? []}
          saving={save.isPending}
          onClose={() => setEditing(null)}
          onSave={(body) => save.mutate({ id: editing === 'new' ? undefined : editing.id, body })}
        />
      )}
      {importing && <ImportNotesModal onClose={() => setImporting(false)} onDone={() => qc.invalidateQueries({ queryKey: ['notes'] })} />}
    </div>
  );
}

function EditModal({
  config,
  row,
  categories,
  saving,
  onClose,
  onSave,
}: {
  config: KindConfig;
  row: Row | null;
  categories: string[];
  saving: boolean;
  onClose: () => void;
  onSave: (body: Record<string, unknown>) => void;
}) {
  const defaults = Object.fromEntries([['name', row?.name ?? ''], ...config.fields.map((f) => [f.key, (row?.[f.key] as string) ?? ''])]);
  const { register, handleSubmit, formState } = useForm<Record<string, string>>({ defaultValues: defaults });
  const submit = handleSubmit((values) => {
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(values)) body[k] = typeof v === 'string' && v.trim() === '' ? null : v;
    onSave(body);
  });
  return (
    <Modal title={`${row ? 'Edit' : 'New'} ${config.singular.toLowerCase()}`} onClose={onClose} wide={config.fields.length > 2}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Name" required error={formState.errors.name && 'Name is required'}>
          <input {...register('name', { required: true })} className={inputClass} autoFocus />
        </Field>
        {config.fields.map((f) => (
          <Field key={f.key} label={f.label} hint={f.hint}>
            {f.type === 'textarea' ? (
              <textarea {...register(f.key)} rows={3} className={inputClass} />
            ) : f.type === 'select' ? (
              <select {...register(f.key)} className={inputClass}>
                <option value="">—</option>
                {(f.key === 'category' ? Array.from(new Set([...(f.options ?? []), ...categories])) : f.options ?? []).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input {...register(f.key)} type={f.type === 'url' ? 'url' : 'text'} className={inputClass} />
            )}
          </Field>
        ))}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ImportNotesModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<NoteImportResult | null>(null);
  const upload = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append('file', file!);
      return (await api.post<NoteImportResult>('/catalog/admin/notes/import', fd)).data;
    },
    onSuccess: (r) => {
      setResult(r);
      onDone();
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });
  return (
    <Modal title="Import notes from CSV" onClose={onClose}>
      {!result ? (
        <div className="space-y-4">
          <p className="text-sm text-gray-300">
            Columns: <code className="text-gold">name</code> and optional <code className="text-gold">category</code>. Existing names are skipped.
          </p>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm text-gray-300" />
          <Button className="w-full" disabled={!file} loading={upload.isPending} onClick={() => upload.mutate()}>
            Upload
          </Button>
        </div>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="text-emerald-300">Inserted: {result.inserted}</div>
          <div className="text-amber-200">Skipped (already exist): {result.skipped}</div>
          {result.errors.length > 0 && <div className="text-red-300">{result.errors.join(' · ')}</div>}
          <Button variant="secondary" className="w-full" onClick={onClose}>
            Done
          </Button>
        </div>
      )}
    </Modal>
  );
}

const NOTE_CATEGORIES = ['Citrus', 'Floral', 'Fruity', 'Green', 'Aquatic', 'Spicy', 'Woody', 'Gourmand', 'Oriental', 'Musky', 'Leather', 'Smoky', 'Mineral', 'Other'] as const;

export const BrandsPage = () => (
  <LookupPage
    config={{
      kind: 'brands',
      title: 'Brands',
      subtitle: 'Houses and designers',
      singular: 'Brand',
      filterParam: 'brand_id',
      fields: [
        { key: 'country', label: 'Country' },
        { key: 'website_url', label: 'Website', type: 'url' },
        { key: 'logo_url', label: 'Logo URL', type: 'url' },
        { key: 'description', label: 'Description', type: 'textarea' },
      ],
      extraColumns: [{ header: 'Country', cell: (r) => (r.country as string) || <span className="text-gray-500">—</span> }],
    }}
  />
);

export const NotesPage = () => (
  <LookupPage
    config={{
      kind: 'notes',
      title: 'Notes',
      subtitle: 'Building blocks of every pyramid',
      singular: 'Note',
      filterParam: undefined,
      fields: [
        { key: 'category', label: 'Category', type: 'select', options: NOTE_CATEGORIES },
        { key: 'description', label: 'Description', type: 'textarea' },
      ],
      extraColumns: [{ header: 'Category', cell: (r) => <Badge tone="gray">{r.category as string}</Badge> }],
    }}
  />
);

export const FamiliesPage = () => (
  <LookupPage
    config={{
      kind: 'families',
      title: 'Families',
      subtitle: 'Olfactive families and their Scent DNA axis',
      singular: 'Family',
      filterParam: 'family_id',
      fields: [
        {
          key: 'axis',
          label: 'Scent DNA axis',
          type: 'select',
          options: RADAR_AXES,
          hint: 'Which of the six radar axes on the mobile Home screen this family counts towards.',
        },
        { key: 'description', label: 'Description', type: 'textarea' },
      ],
      extraColumns: [
        {
          header: 'Radar axis',
          cell: (r) => (r.axis ? <Badge>{r.axis as string}</Badge> : <Badge tone="red">not set</Badge>),
        },
      ],
    }}
  />
);

export const AccordsPage = () => (
  <LookupPage
    config={{ kind: 'accords', title: 'Accords', subtitle: 'Main accords', singular: 'Accord', filterParam: 'accord_id', fields: [] }}
  />
);

export const OccasionsPage = () => (
  <LookupPage
    config={{
      kind: 'occasions',
      title: 'Occasions',
      subtitle: 'Used by search filters and the daily pick',
      singular: 'Occasion',
      filterParam: 'occasion_id',
      fields: [],
    }}
  />
);
