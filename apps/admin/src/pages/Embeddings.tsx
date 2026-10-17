import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Cpu, RefreshCw, Sparkles, Zap } from 'lucide-react';
import type { EmbeddingResult, EmbeddingStatus, FragranceListItem, JobAccepted, OllamaHealth, Page } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { shortDate } from '../lib/hooks';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Badge, Button, Card, Modal, PageHeader } from '../components/ui';

const isDone = (s?: EmbeddingStatus) => !!s && s.missing === 0 && s.stale === 0 && s.other_model === 0;

export default function Embeddings() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [polling, setPolling] = useState(false);
  const [viewing, setViewing] = useState<EmbeddingResult | null>(null);

  const status = useQuery({
    queryKey: ['embedding-status'],
    queryFn: () => api.get<EmbeddingStatus>('/catalog/admin/embeddings/status').then((r) => r.data),
    refetchInterval: (q) => (polling && !isDone(q.state.data) ? 2000 : false),
  });
  const llm = useQuery({ queryKey: ['ai-health'], queryFn: () => api.get<OllamaHealth>('/ai/health').then((r) => r.data) });
  const missing = useQuery({
    queryKey: ['fragrances', 'missing-embedding', page],
    queryFn: () => api.get<Page<FragranceListItem>>('/catalog/fragrances', { params: { missing: 'embedding', page, size: 15, sort: 'updated' } }).then((r) => r.data),
    refetchInterval: polling && !isDone(status.data) ? 3000 : false,
  });

  const s = status.data;
  const updating = polling && !isDone(s);

  const regenerate = useMutation({
    mutationFn: (onlyMissing: boolean) => api.post<JobAccepted>('/catalog/admin/embeddings/regenerate', { only_missing: onlyMissing }).then((r) => r.data),
    onSuccess: (r) => {
      toast(`${r.detail} — running in the background`, 'info');
      setPolling(true);
      setTimeout(() => setPolling(false), 120_000);
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const generateOne = useMutation({
    mutationFn: (id: number) => api.post<EmbeddingResult>('/catalog/admin/embeddings/generate', { fragrance_id: id }).then((r) => r.data),
    onSuccess: (r) => {
      setViewing(r);
      qc.invalidateQueries({ queryKey: ['embedding-status'] });
      qc.invalidateQueries({ queryKey: ['fragrances'] });
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const columns: Column<FragranceListItem>[] = [
    { header: 'Fragrance', cell: (r) => <span className="text-white font-medium">{r.brand_name} — {r.name}</span> },
    { header: 'Notes', cell: (r) => r.note_count || <Badge tone="red">none</Badge> },
    { header: 'Added', cell: (r) => shortDate(r.created_at) },
    {
      header: '',
      cell: (r) => (
        <Button variant="secondary" className="py-1.5" loading={generateOne.isPending && generateOne.variables === r.id} onClick={() => generateOne.mutate(r.id)}>
          <Zap className="w-3.5 h-3.5" /> Embed now
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Embeddings"
        subtitle="Vectors behind similarity, dupes, recommendations and AI search"
        actions={
          <>
            <Button variant="secondary" onClick={() => regenerate.mutate(true)} loading={regenerate.isPending}>
              <Sparkles className="w-4 h-4" /> Fix missing & stale
            </Button>
            <Button
              onClick={() => confirm('Regenerate every vector? Searches keep working while it runs.') && regenerate.mutate(false)}
              loading={regenerate.isPending}
            >
              <RefreshCw className="w-4 h-4" /> Regenerate all
            </Button>
          </>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-gold" /> Coverage
            </h2>
            {updating && <Badge tone="blue">updating…</Badge>}
          </div>
          {s ? (
            <>
              <div className="mt-4 h-3 rounded-full bg-navy-dark overflow-hidden" role="progressbar" aria-valuenow={s.coverage_pct} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-full bg-gradient-to-r from-gold-dark to-gold transition-all" style={{ width: `${s.coverage_pct}%` }} />
              </div>
              <div className="mt-2 text-sm text-gray-300">
                <span className="text-white font-bold">{s.with_embedding}</span> of {s.total_fragrances} fragrances embedded ({s.coverage_pct}%)
              </div>
              <div className="grid grid-cols-3 gap-3 mt-5">
                <Stat label="Missing" value={s.missing} warn={s.missing > 0} />
                <Stat label="Stale (edited since)" value={s.stale} warn={s.stale > 0} />
                <Stat label="Other model" value={s.other_model} warn={s.other_model > 0} />
              </div>
            </>
          ) : (
            <div className="h-24 mt-4 rounded-xl bg-navy-dark animate-pulse" />
          )}
        </Card>
        <Card>
          <h2 className="font-semibold text-white mb-3">Engines</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Embedding provider" value={s?.provider} />
            <Row label="Model" value={s?.model_version} />
            <Row label="Last generated" value={s?.last_generated_at ? new Date(s.last_generated_at).toLocaleString() : '—'} />
            <Row label="Job queue" value={s?.job_queue} />
            <Row label="LLM (Ollama)" value={llm.data ? `${llm.data.status}${llm.data.models.length ? ` · ${llm.data.default_model}` : ''}` : '…'} />
          </dl>
          {s?.provider === 'hashing' && (
            <p className="mt-4 text-xs text-amber-200 bg-amber-500/10 border border-amber-500/25 rounded-lg p-3">
              Using the lightweight hashing embedder. Install the API’s <code>ml</code> extra for real semantic similarity, then “Regenerate all”.
            </p>
          )}
          {llm.data?.hint && <p className="mt-3 text-xs text-gray-400">{llm.data.hint}</p>}
        </Card>
      </div>
      <div>
        <h2 className="font-serif text-lg text-white mb-3">Fragrances without a vector</h2>
        <DataTable
          columns={columns}
          rows={missing.data?.items ?? []}
          rowKey={(r) => r.id}
          isLoading={missing.isLoading}
          page={page}
          total={missing.data?.total ?? 0}
          size={15}
          onPage={setPage}
          empty="Every fragrance has a vector. 🎉"
        />
      </div>
      {viewing && (
        <Modal title="Generated embedding" onClose={() => setViewing(null)} wide>
          <p className="text-xs text-gray-400 mb-2">
            {viewing.model_version} · {new Date(viewing.generated_at).toLocaleString()}
          </p>
          <p className="text-sm text-gray-100 bg-navy-dark rounded-xl p-4 leading-relaxed">{viewing.text_input}</p>
        </Modal>
      )}
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn: boolean }) {
  return (
    <div className="bg-navy-dark rounded-xl p-3 border border-white/[0.06]">
      <div className={warn ? 'text-amber-200 text-xl font-bold' : 'text-emerald-300 text-xl font-bold'}>{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-gray-400 mt-1">{label}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-gray-400">{label}</dt>
      <dd className="text-gray-100 text-right truncate">{value ?? '…'}</dd>
    </div>
  );
}
