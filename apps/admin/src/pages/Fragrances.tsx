import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useFieldArray, useForm, type UseFormReturn } from 'react-hook-form';
import { useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Check, DollarSign, Droplets, Edit2, Eye, Layers, Plus, Save, Search, Tag, ThermometerSun, Trash2, X, Zap,
} from 'lucide-react';
import clsx from 'clsx';
import type {
  AccordOut, BrandOut, EmbeddingTextPreview, FamilyOut, FragranceDetail, FragranceIn, FragranceListItem, NoteOut,
  OccasionOut, Page,
} from '@api-types';
import { CONCENTRATIONS, GENDERS, SILLAGES } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { shortDate, useDebounce, usd } from '../lib/hooks';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Badge, Button, Card, Field, PageHeader, inputClass } from '../components/ui';

type Position = 'top' | 'heart' | 'base';
const POSITIONS: Position[] = ['top', 'heart', 'base'];
const PAGE_SIZE = 20;
const DRAFT_KEY = 'scentvault_fragrance_draft';
const FILTER_LABELS: Record<string, string> = {
  missing: 'Missing',
  brand_id: 'Brand',
  family_id: 'Family',
  accord_id: 'Accord',
  occasion_id: 'Occasion',
};

function useLookup<T>(kind: string) {
  return useQuery({
    queryKey: ['lookups', kind],
    queryFn: () => api.get<Page<T>>(`/catalog/${kind}`, { params: { size: 500 } }).then((r) => r.data.items),
    staleTime: 5 * 60 * 1000,
  });
}

function useLookups() {
  const brands = useLookup<BrandOut>('brands');
  const notes = useLookup<NoteOut>('notes');
  const families = useLookup<FamilyOut>('families');
  const accords = useLookup<AccordOut>('accords');
  const occasions = useLookup<OccasionOut>('occasions');
  return {
    brands: brands.data ?? [],
    notes: notes.data ?? [],
    families: families.data ?? [],
    accords: accords.data ?? [],
    occasions: occasions.data ?? [],
    ready: !!(brands.data && notes.data),
  };
}

// ═══════════════════════════════════════════════════════════════════
// List
// ═══════════════════════════════════════════════════════════════════

export default function Fragrances() {
  const [params, setParams] = useSearchParams();
  const [editingId, setEditingId] = useState<number | 'new' | null>(null);
  const [search, setSearch] = useState('');
  const [concentration, setConcentration] = useState('');
  const [gender, setGender] = useState('');
  const [sort, setSort] = useState('newest');
  const debounced = useDebounce(search);
  const qc = useQueryClient();
  const toast = useToast();
  const lookups = useLookups();

  const urlFilters = Object.fromEntries(Object.keys(FILTER_LABELS).flatMap((k) => (params.get(k) ? [[k, params.get(k)!]] : [])));
  const filterKey = JSON.stringify(urlFilters);
  // Any filter change sends you back to page 1 (derived, so no effect needed).
  const filterSig = JSON.stringify([debounced, concentration, gender, filterKey, sort]);
  const [pageState, setPageState] = useState({ sig: filterSig, page: 1 });
  const page = pageState.sig === filterSig ? pageState.page : 1;
  const setPage = (p: number) => setPageState({ sig: filterSig, page: p });

  const { data, isLoading } = useQuery({
    queryKey: ['fragrances', page, debounced, concentration, gender, sort, filterKey],
    queryFn: () =>
      api
        .get<Page<FragranceListItem>>('/catalog/fragrances', {
          params: { page, size: PAGE_SIZE, search: debounced || undefined, concentration: concentration || undefined, gender: gender || undefined, sort, ...urlFilters },
        })
        .then((r) => r.data),
    placeholderData: (prev) => prev,
  });

  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/catalog/admin/fragrances/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fragrances'] });
      toast('Fragrance deleted');
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const filterName = (k: string, v: string) => {
    const id = Number(v);
    const pools: Record<string, { id: number; name: string }[]> = {
      brand_id: lookups.brands,
      family_id: lookups.families,
      accord_id: lookups.accords,
      occasion_id: lookups.occasions,
    };
    return pools[k]?.find((x) => x.id === id)?.name ?? v;
  };

  const columns: Column<FragranceListItem>[] = [
    {
      header: 'Fragrance',
      sortKey: 'name',
      cell: (r) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-navy-dark rounded-lg border border-white/10 flex items-center justify-center overflow-hidden shrink-0">
            {r.image_url ? <img src={r.image_url} alt="" className="w-full h-full object-cover" /> : <span className="font-serif text-gold">{r.brand_name[0]}</span>}
          </div>
          <div>
            <div className="font-semibold text-white leading-tight">{r.name}</div>
            <div className="text-[11px] text-gold uppercase tracking-wider">{r.brand_name}</div>
          </div>
        </div>
      ),
    },
    { header: 'Brand', sortKey: 'brand', cell: (r) => r.brand_name, className: 'hidden xl:table-cell' },
    { header: 'Type', cell: (r) => `${r.concentration} · ${r.gender}` },
    { header: 'Year', sortKey: 'year', cell: (r) => r.release_year ?? '—' },
    { header: 'Notes', cell: (r) => (r.note_count ? r.note_count : <Badge tone="red">none</Badge>) },
    { header: 'From', cell: (r) => usd(r.min_price_usd) },
    {
      header: 'Vector',
      cell: (r) => (
        <Badge tone={r.has_embedding ? 'green' : 'red'}>
          <Zap className="w-3 h-3" /> {r.has_embedding ? 'yes' : 'no'}
        </Badge>
      ),
    },
    { header: 'Added', sortKey: 'newest', cell: (r) => <span className="text-gray-400 text-xs">{shortDate(r.created_at)}</span> },
    {
      header: 'Actions',
      cell: (r) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => setEditingId(r.id)} className="p-1.5 text-gold hover:bg-gold/10 rounded" aria-label={`Edit ${r.name}`}>
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => confirm(`Delete “${r.brand_name} ${r.name}”? Collection entries using it will be removed too.`) && del.mutate(r.id)}
            className="p-1.5 text-red-300 hover:bg-red-400/10 rounded"
            aria-label={`Delete ${r.name}`}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  if (editingId !== null) {
    return (
      <FragranceEditor
        id={editingId === 'new' ? null : editingId}
        lookups={lookups}
        onClose={(next) => {
          qc.invalidateQueries({ queryKey: ['fragrances'] });
          setEditingId(null);
          if (next === 'new') setTimeout(() => setEditingId('new'), 0);
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fragrances"
        subtitle="Catalog"
        actions={
          <Button onClick={() => setEditingId('new')}>
            <Plus className="w-4 h-4" /> New fragrance
          </Button>
        }
      />
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input className={`${inputClass} pl-11`} placeholder="Search name or brand…" aria-label="Search fragrances" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className={`${inputClass} w-44`} aria-label="Concentration" value={concentration} onChange={(e) => setConcentration(e.target.value)}>
          <option value="">All concentrations</option>
          {CONCENTRATIONS.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select className={`${inputClass} w-40`} aria-label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}>
          <option value="">All genders</option>
          {GENDERS.map((g) => (
            <option key={g}>{g}</option>
          ))}
        </select>
      </div>
      {Object.keys(urlFilters).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(urlFilters).map(([k, v]) => (
            <button
              key={k}
              onClick={() => {
                params.delete(k);
                setParams(params);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gold/10 border border-gold/30 text-gold text-xs font-bold"
            >
              {FILTER_LABELS[k]}: {k === 'missing' ? v : filterName(k, v)} <X className="w-3 h-3" />
            </button>
          ))}
        </div>
      )}
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(r) => r.id}
        isLoading={isLoading}
        sort={sort}
        onSort={setSort}
        page={page}
        total={data?.total ?? 0}
        size={PAGE_SIZE}
        onPage={setPage}
        onRowClick={(r) => setEditingId(r.id)}
        empty="No fragrances match. Clear the filters or add one."
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Editor
// ═══════════════════════════════════════════════════════════════════

type NoteRow = { note_id: number; position: Position; prominence: number; name: string };
type FormValues = Omit<FragranceIn, 'notes' | 'release_year' | 'longevity_hours'> & {
  notes: NoteRow[];
  release_year?: number | string | null;
  longevity_hours?: number | string | null;
};

const EMPTY: FormValues = {
  name: '',
  brand_id: 0,
  concentration: 'EDP',
  gender: 'Unisex',
  sillage: 'Moderate',
  description: '',
  image_url: '',
  discontinued: false,
  season_spring: false,
  season_summer: false,
  season_fall: false,
  season_winter: false,
  notes: [],
  family_ids: [],
  accord_ids: [],
  occasion_ids: [],
  prices: [{ size_ml: 100, price_usd: 0 }],
  release_year: '',
  longevity_hours: '',
};

const TABS = [
  { key: 'basics', label: 'Basics', icon: Droplets },
  { key: 'pyramid', label: 'Pyramid', icon: Layers },
  { key: 'classification', label: 'Classification', icon: Tag },
  { key: 'seasons', label: 'Seasons & occasions', icon: ThermometerSun },
  { key: 'prices', label: 'Prices', icon: DollarSign },
] as const;
type TabKey = (typeof TABS)[number]['key'];

function toPayload(v: FormValues): FragranceIn {
  const num = (x: unknown) => (x === '' || x == null || Number.isNaN(Number(x)) ? null : Number(x));
  return {
    name: v.name.trim(),
    brand_id: Number(v.brand_id),
    concentration: v.concentration,
    gender: v.gender,
    sillage: v.sillage || null,
    release_year: num(v.release_year),
    longevity_hours: num(v.longevity_hours),
    description: v.description?.trim() || null,
    image_url: v.image_url?.trim() || null,
    discontinued: !!v.discontinued,
    season_spring: !!v.season_spring,
    season_summer: !!v.season_summer,
    season_fall: !!v.season_fall,
    season_winter: !!v.season_winter,
    notes: v.notes.map((n) => ({ note_id: n.note_id, position: n.position, prominence: n.prominence })),
    family_ids: v.family_ids ?? [],
    accord_ids: v.accord_ids ?? [],
    occasion_ids: v.occasion_ids ?? [],
    prices: (v.prices ?? []).filter((p) => Number(p.size_ml) > 0).map((p) => ({ size_ml: Number(p.size_ml), price_usd: Number(p.price_usd) || 0 })),
  };
}

function fromDetail(d: FragranceDetail): FormValues {
  return {
    ...EMPTY,
    name: d.name,
    brand_id: d.brand_id,
    concentration: d.concentration,
    gender: d.gender,
    sillage: d.sillage ?? 'Moderate',
    release_year: d.release_year ?? '',
    longevity_hours: d.longevity_hours ?? '',
    description: d.description ?? '',
    image_url: d.image_url ?? '',
    discontinued: d.discontinued,
    season_spring: d.season_spring,
    season_summer: d.season_summer,
    season_fall: d.season_fall,
    season_winter: d.season_winter,
    notes: d.notes.map((n) => ({ note_id: n.note_id, position: n.position, prominence: n.prominence, name: n.name })),
    family_ids: d.families.map((f) => f.id),
    accord_ids: d.accords.map((a) => a.id),
    occasion_ids: d.occasions.map((o) => o.id),
    prices: d.prices.length ? d.prices.map((p) => ({ size_ml: p.size_ml, price_usd: p.price_usd })) : EMPTY.prices,
  };
}

function FragranceEditor({ id, lookups, onClose }: { id: number | null; lookups: ReturnType<typeof useLookups>; onClose: (next?: 'new') => void }) {
  const toast = useToast();
  const [tab, setTab] = useState<TabKey>('basics');
  const [hasDraft, setHasDraft] = useState(false);
  const form = useForm<FormValues>({ defaultValues: EMPTY });
  const { register, handleSubmit, reset, watch, formState } = form;

  const { data: detail, isLoading } = useQuery({
    queryKey: ['fragrance', id],
    queryFn: () => api.get<FragranceDetail>(`/catalog/fragrances/${id}`).then((r) => r.data),
    enabled: id !== null,
  });
  useEffect(() => {
    if (detail) reset(fromDetail(detail));
  }, [detail, reset]);

  // Draft autosave for new fragrances
  const values = watch();
  useEffect(() => {
    if (id !== null) return;
    try {
      setHasDraft(!!JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')?.name);
    } catch {
      /* ignore */
    }
  }, [id]);
  useEffect(() => {
    if (id !== null || !values.name) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(values));
      } catch {
        /* ignore */
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [id, values]);

  // Live embedding-text preview
  const payloadKey = JSON.stringify(toPayload(values));
  const debouncedPayload = useDebounce(payloadKey, 600);
  const preview = useQuery({
    queryKey: ['embedding-preview', debouncedPayload],
    queryFn: () => api.post<EmbeddingTextPreview>('/catalog/admin/fragrances/embedding-preview', JSON.parse(debouncedPayload)).then((r) => r.data.text),
    enabled: Number(values.brand_id) > 0 && !!values.name,
    placeholderData: (p) => p,
  });

  const save = useMutation({
    mutationFn: (v: FormValues) => {
      const body = toPayload(v);
      return id ? api.put<FragranceDetail>(`/catalog/admin/fragrances/${id}`, body) : api.post<FragranceDetail>('/catalog/admin/fragrances', body);
    },
    onError: (e) => toast(errorMessage(e, 'Save failed'), 'error'),
  });

  const submit = (next?: 'new') =>
    handleSubmit(
      (v) =>
        save.mutate(v, {
          onSuccess: (res) => {
            try {
              localStorage.removeItem(DRAFT_KEY);
            } catch {
              /* ignore */
            }
            toast(`${res.data.name} ${id ? 'updated' : 'created'} — embedding queued`);
            onClose(next);
          },
        }),
      (errors) => {
        setTab(errors.name || errors.brand_id ? 'basics' : tab);
        toast('Fill in the required fields first', 'error');
      },
    )();

  const issues = [
    !values.notes.length && 'No notes yet — similarity will be weak',
    !values.family_ids?.length && 'No family — Scent DNA can’t use it',
    !(values.season_spring || values.season_summer || values.season_fall || values.season_winter) && 'No season selected',
    !values.prices?.some((p) => Number(p.price_usd) > 0) && 'No retail price — dupes and budget search skip it',
  ].filter(Boolean) as string[];

  return (
    <div className="pb-24">
      <div className="sticky top-16 z-20 bg-navy/90 backdrop-blur-xl border-b border-white/[0.08] -mx-6 lg:-mx-8 px-6 lg:px-8 py-3 flex flex-wrap gap-3 justify-between items-center mb-6">
        <button onClick={() => onClose()} className="text-gray-300 hover:text-white flex items-center">
          <ArrowLeft className="w-5 h-5 mr-2" /> Back to list
        </button>
        <div className="flex gap-3">
          {!id && (
            <Button variant="secondary" onClick={() => submit('new')} loading={save.isPending}>
              <Plus className="w-4 h-4" /> Save & add another
            </Button>
          )}
          <Button onClick={() => submit()} loading={save.isPending}>
            <Save className="w-4 h-4" /> {id ? 'Save changes' : 'Create fragrance'}
          </Button>
        </div>
      </div>

      {hasDraft && !id && (
        <div className="bg-sky-500/10 border border-sky-500/25 rounded-xl p-4 mb-6 flex items-center justify-between gap-3">
          <span className="text-sky-200 text-sm">You have an unsaved draft.</span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                try {
                  reset(JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}'));
                } catch {
                  /* ignore */
                }
                setHasDraft(false);
              }}
            >
              Restore
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                localStorage.removeItem(DRAFT_KEY);
                setHasDraft(false);
              }}
            >
              Discard
            </Button>
          </div>
        </div>
      )}

      {id !== null && isLoading ? (
        <div className="h-64 rounded-2xl bg-navy-light animate-pulse" />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-8 space-y-4">
            <div role="tablist" className="flex flex-wrap gap-1 bg-navy-dark p-1 rounded-xl border border-white/[0.08]">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  role="tab"
                  aria-selected={tab === t.key}
                  onClick={() => setTab(t.key)}
                  className={clsx(
                    'flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors',
                    tab === t.key ? 'bg-gold/15 text-gold' : 'text-gray-300 hover:text-white',
                  )}
                >
                  <t.icon className="w-4 h-4" /> {t.label}
                </button>
              ))}
            </div>
            <Card>
              {tab === 'basics' && (
                <div className="space-y-5">
                  <Field label="Name" required error={formState.errors.name && 'Name is required'}>
                    <input {...register('name', { required: true })} className={inputClass} autoFocus={!id} />
                  </Field>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Field label="Brand" required error={formState.errors.brand_id && 'Choose a brand'}>
                      <select {...register('brand_id', { valueAsNumber: true, validate: (v) => Number(v) > 0 })} className={inputClass}>
                        <option value={0}>Select brand…</option>
                        {lookups.brands.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Concentration">
                      <select {...register('concentration')} className={inputClass}>
                        {CONCENTRATIONS.map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Gender">
                      <select {...register('gender')} className={inputClass}>
                        {GENDERS.map((g) => (
                          <option key={g}>{g}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Release year">
                      <input type="number" {...register('release_year')} placeholder="e.g. 2023" className={inputClass} />
                    </Field>
                    <Field label="Sillage">
                      <select {...register('sillage')} className={inputClass}>
                        {SILLAGES.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Longevity (hours)">
                      <input type="number" step="0.5" {...register('longevity_hours')} placeholder="e.g. 8" className={inputClass} />
                    </Field>
                  </div>
                  <Field label="Image URL" hint="Shown on the mobile app; a brand initial is used when empty.">
                    <input type="url" {...register('image_url')} placeholder="https://…" className={inputClass} />
                  </Field>
                  <Field label="Description">
                    <textarea {...register('description')} rows={3} className={inputClass} />
                  </Field>
                  <label className="flex items-center gap-3 cursor-pointer text-sm text-gray-200">
                    <input type="checkbox" {...register('discontinued')} className="w-4 h-4 accent-[#c9a96e]" /> Discontinued (excluded from recommendations)
                  </label>
                </div>
              )}
              {tab === 'pyramid' && <PyramidEditor form={form} notes={lookups.notes} />}
              {tab === 'classification' && (
                <div className="space-y-6">
                  <ChipPicker form={form} field="family_ids" title="Families" items={lookups.families} hint={(f) => (f as FamilyOut).axis ?? undefined} />
                  <ChipPicker form={form} field="accord_ids" title="Accords" items={lookups.accords} />
                </div>
              )}
              {tab === 'seasons' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-gold uppercase tracking-wider mb-3">Seasons</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {(['spring', 'summer', 'fall', 'winter'] as const).map((s) => {
                        const key = `season_${s}` as const;
                        const on = watch(key);
                        return (
                          <label key={s} className={clsx('flex items-center justify-center p-4 rounded-xl border-2 cursor-pointer font-bold text-xs uppercase', on ? 'bg-gold/10 border-gold/50 text-gold' : 'bg-navy-dark border-transparent text-gray-400 hover:border-white/10')}>
                            <input type="checkbox" {...register(key)} className="sr-only" /> {s}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  <ChipPicker form={form} field="occasion_ids" title="Occasions" items={lookups.occasions} />
                </div>
              )}
              {tab === 'prices' && <PricesEditor form={form} />}
            </Card>
          </div>

          <div className="xl:col-span-4 space-y-4">
            <Card>
              <h3 className="text-sm font-bold text-gold uppercase tracking-wider mb-2 flex items-center gap-2">
                <Eye className="w-4 h-4" /> What the model will see
              </h3>
              <p className="text-xs text-gray-400 mb-3">Similarity, dupes and AI search all work from this text. Update it by editing the form.</p>
              <p className="text-sm text-gray-100 leading-relaxed bg-navy-dark rounded-xl p-4 border border-white/[0.06] min-h-[96px]">
                {preview.data ?? <span className="text-gray-500">Pick a brand and name to see the preview.</span>}
              </p>
            </Card>
            <Card>
              <h3 className="text-sm font-bold text-gold uppercase tracking-wider mb-3">Completeness</h3>
              {issues.length === 0 ? (
                <p className="text-sm text-emerald-300 flex items-center gap-2">
                  <Check className="w-4 h-4" /> Looks complete
                </p>
              ) : (
                <ul className="space-y-2 text-sm text-amber-200">
                  {issues.map((i) => (
                    <li key={i}>• {i}</li>
                  ))}
                </ul>
              )}
            </Card>
            {values.image_url && (
              <Card>
                <img src={values.image_url} alt="Bottle preview" className="rounded-xl max-h-64 mx-auto" />
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PyramidEditor({ form, notes }: { form: UseFormReturn<FormValues>; notes: NoteOut[] }) {
  const { watch, setValue } = form;
  const current = watch('notes');
  const [query, setQuery] = useState<Record<Position, string>>({ top: '', heart: '', base: '' });
  const refs = useRef<Record<Position, HTMLInputElement | null>>({ top: null, heart: null, base: null });

  const filtered = (pos: Position) => {
    const q = query[pos].toLowerCase();
    return notes.filter((n) => (!q || n.name.toLowerCase().includes(q)) && !current.some((c) => c.note_id === n.id && c.position === pos)).slice(0, 8);
  };
  const add = (n: NoteOut, pos: Position) => {
    setValue('notes', [...current, { note_id: n.id, position: pos, prominence: 3, name: n.name }], { shouldDirty: true });
    setQuery((q) => ({ ...q, [pos]: '' }));
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>, pos: Position) => {
    const i = POSITIONS.indexOf(pos);
    if (e.key === 'Enter') {
      e.preventDefault();
      const first = filtered(pos)[0];
      if (first && query[pos]) add(first, pos);
    } else if (e.key === 'Tab' && !e.shiftKey && i < 2) {
      e.preventDefault();
      refs.current[POSITIONS[i + 1]]?.focus();
    } else if (e.key === 'Tab' && e.shiftKey && i > 0) {
      e.preventDefault();
      refs.current[POSITIONS[i - 1]]?.focus();
    }
  };

  return (
    <div>
      <p className="text-gray-400 text-xs mb-4">Type to search · Enter adds the first match · Tab jumps to the next tier · dots set prominence</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {POSITIONS.map((pos) => {
          const rows = current.filter((n) => n.position === pos);
          const matches = filtered(pos);
          return (
            <div key={pos} className="flex flex-col bg-navy-dark/50 rounded-xl border border-white/[0.08] overflow-hidden min-h-[360px]">
              <div className={clsx('p-2.5 text-center text-[11px] font-black uppercase tracking-widest', pos === 'top' ? 'bg-[#E8C97A] text-navy' : pos === 'heart' ? 'bg-[#C9A96E] text-navy' : 'bg-[#8B6F3A] text-white')}>
                {pos} ({rows.length})
              </div>
              <div className="p-2 border-b border-white/[0.06] relative">
                <input
                  ref={(el) => {
                    refs.current[pos] = el;
                  }}
                  value={query[pos]}
                  onChange={(e) => setQuery((q) => ({ ...q, [pos]: e.target.value }))}
                  onKeyDown={(e) => onKey(e, pos)}
                  placeholder="Add note…"
                  aria-label={`Add ${pos} note`}
                  className="w-full bg-transparent text-sm text-gray-100 px-2 py-1.5 outline-none border border-white/10 rounded-lg focus:border-gold/40 placeholder:text-gray-500"
                />
                {query[pos] && matches.length > 0 && (
                  <div className="absolute left-2 right-2 top-full mt-1 z-10 bg-navy-dark rounded-lg border border-white/10 shadow-xl">
                    {matches.map((n) => (
                      <button key={n.id} type="button" onClick={() => add(n, pos)} className="w-full text-left px-3 py-1.5 text-sm text-gray-200 hover:bg-gold/10 hover:text-gold">
                        {n.name} <span className="text-gray-500 text-xs">{n.category}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex-1 p-2 space-y-1.5">
                {rows.map((n) => (
                  <div key={`${n.note_id}-${pos}`} className="group flex items-center justify-between bg-white/[0.04] px-2.5 py-1.5 rounded-lg">
                    <span className="text-sm text-gray-100 truncate">{n.name}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      {[1, 2, 3, 4, 5].map((dot) => (
                        <button
                          key={dot}
                          type="button"
                          aria-label={`Prominence ${dot} of 5`}
                          onClick={() => setValue('notes', current.map((x) => (x.note_id === n.note_id && x.position === pos ? { ...x, prominence: dot } : x)))}
                          className={clsx('w-2 h-2 rounded-full', dot <= n.prominence ? 'bg-gold' : 'bg-white/15')}
                        />
                      ))}
                      <button type="button" aria-label={`Remove ${n.name}`} onClick={() => setValue('notes', current.filter((x) => !(x.note_id === n.note_id && x.position === pos)))} className="ml-1 text-red-300 opacity-60 group-hover:opacity-100">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
                {rows.length === 0 && <div className="text-center text-gray-500 text-xs py-6">No {pos} notes</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ChipPicker({
  form,
  field,
  title,
  items,
  hint,
}: {
  form: UseFormReturn<FormValues>;
  field: 'family_ids' | 'accord_ids' | 'occasion_ids';
  title: string;
  items: { id: number; name: string }[];
  hint?: (item: { id: number; name: string }) => string | undefined;
}) {
  const selected = form.watch(field) ?? [];
  const [filter, setFilter] = useState('');
  const shown = useMemo(() => items.filter((i) => !filter || i.name.toLowerCase().includes(filter.toLowerCase())), [items, filter]);
  const toggle = (id: number) => form.setValue(field, selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id], { shouldDirty: true });
  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-bold text-gold uppercase tracking-wider">
          {title} <span className="text-gray-400">({selected.length})</span>
        </h3>
        {items.length > 12 && (
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter…" aria-label={`Filter ${title}`} className="bg-navy-dark border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-100 outline-none w-40" />
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {shown.map((i) => {
          const on = selected.includes(i.id);
          const h = hint?.(i);
          return (
            <button
              key={i.id}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(i.id)}
              className={clsx('px-3 py-1.5 rounded-full text-sm border transition-all', on ? 'bg-gold/15 border-gold/50 text-gold' : 'bg-navy-dark border-white/10 text-gray-300 hover:border-white/25')}
            >
              {on && <Check className="w-3 h-3 inline mr-1" />}
              {i.name}
              {h && <span className="ml-1.5 text-[10px] uppercase opacity-70">{h}</span>}
            </button>
          );
        })}
        {items.length === 0 && <p className="text-gray-400 text-sm">Nothing defined yet — add some on its page.</p>}
      </div>
    </div>
  );
}

function PricesEditor({ form }: { form: UseFormReturn<FormValues> }) {
  const { control, register, watch } = form;
  const { fields, append, remove } = useFieldArray({ control, name: 'prices' });
  const prices = watch('prices') ?? [];
  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-400">Reference retail prices (USD) per size. Spotted prices go in the Price logger.</p>
      <div className="flex flex-wrap gap-2">
        {[10, 30, 50, 75, 100, 125, 200].map((ml) => (
          <button
            key={ml}
            type="button"
            onClick={() => !prices.some((p) => Number(p.size_ml) === ml) && append({ size_ml: ml, price_usd: 0 })}
            className="px-2.5 py-1 bg-navy-dark border border-white/10 rounded-lg text-xs font-bold text-gray-300 hover:text-gold hover:border-gold/30"
          >
            + {ml} ml
          </button>
        ))}
      </div>
      {fields.map((f, i) => (
        <div key={f.id} className="flex gap-3 items-end">
          <div className="flex-1">
            <Field label="Size (ml)">
              <input type="number" {...register(`prices.${i}.size_ml`, { valueAsNumber: true })} className={inputClass} />
            </Field>
          </div>
          <div className="flex-1">
            <Field label="Price (USD)">
              <input type="number" step="0.01" {...register(`prices.${i}.price_usd`, { valueAsNumber: true })} className={inputClass} />
            </Field>
          </div>
          <div className="w-24 pb-3 text-xs text-gray-400">
            {Number(prices[i]?.size_ml) > 0 && Number(prices[i]?.price_usd) > 0 ? `${usd(Number(prices[i].price_usd) / Number(prices[i].size_ml))}/ml` : ''}
          </div>
          <button type="button" onClick={() => remove(i)} className="mb-2 p-2 text-red-300 hover:bg-red-400/10 rounded" aria-label="Remove size">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => append({ size_ml: 100, price_usd: 0 })} className="w-full py-3 border-2 border-dashed border-white/10 rounded-xl text-sm font-bold text-gray-300 hover:text-gold hover:border-gold/30">
        + Add size
      </button>
    </div>
  );
}
