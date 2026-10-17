import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowRight, CheckCircle2, Cpu, DollarSign, Droplets, Tag, UserPlus, Users } from 'lucide-react';
import type { AdminStats, WorkQueue } from '@api-types';
import api from '../lib/api';
import { Card, PageHeader } from '../components/ui';

// Keys match AdminService.QUEUES in the API (and the `missing` filter of /catalog/fragrances).
const QUEUE_LINKS: Record<string, string> = {
  embedding: '/embeddings',
  stale_embedding: '/embeddings',
  notes: '/fragrances?missing=notes',
  families: '/fragrances?missing=families',
  image: '/fragrances?missing=image',
  prices: '/fragrances?missing=prices',
  stale_prices: '/price-logger',
};

function QueueCard({ q }: { q: WorkQueue }) {
  const done = q.count === 0;
  return (
    <Card className="flex flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {done ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertCircle className="w-5 h-5 text-amber-300" />}
          <h2 className="font-semibold text-white">{q.label}</h2>
        </div>
        <span className={done ? 'text-emerald-300 font-bold' : 'text-amber-200 font-bold text-lg'}>{q.count}</span>
      </div>
      {done ? (
        <p className="text-sm text-gray-400 mt-3">All clear.</p>
      ) : (
        <ul className="mt-3 space-y-1.5 flex-1">
          {q.items.map((i) => (
            <li key={i.id} className="text-sm flex justify-between gap-3">
              <span className="truncate text-gray-200">
                {i.name} <span className="text-gray-400">· {i.brand_name}</span>
              </span>
              {i.detail && <span className="text-xs text-gray-400 shrink-0">{i.detail}</span>}
            </li>
          ))}
        </ul>
      )}
      {!done && (
        <Link to={QUEUE_LINKS[q.key] ?? '/fragrances'} className="mt-4 inline-flex items-center gap-1 text-sm text-gold hover:text-gold-light font-medium">
          Work through these <ArrowRight className="w-4 h-4" />
        </Link>
      )}
    </Card>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api.get<AdminStats>('/admin/stats').then((r) => r.data),
  });

  const tiles = data
    ? [
        { label: 'Fragrances', value: data.counts.fragrances, icon: Droplets, to: '/fragrances' },
        { label: 'Brands', value: data.counts.brands, icon: Tag, to: '/brands' },
        { label: 'Users', value: data.counts.users, icon: Users, to: '/users' },
        { label: 'New users (7 days)', value: data.new_users_7d, icon: UserPlus, to: '/users' },
        { label: 'Prices logged today', value: data.price_logs_today, icon: DollarSign, to: '/price-logger' },
        { label: 'Embeddings missing / stale', value: `${data.embeddings_missing} / ${data.embeddings_stale}`, icon: Cpu, to: '/embeddings' },
      ]
    : [];

  return (
    <div className="space-y-8">
      <PageHeader title="Work queue" subtitle="What the catalog needs next" />
      {isError && <Card className="text-red-200">Couldn’t load stats. Is the API running?</Card>}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {isLoading && Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-28 rounded-2xl bg-navy-light animate-pulse" />)}
        {tiles.map((t) => (
          <Link key={t.label} to={t.to} className="bg-navy-light border border-white/[0.08] p-5 rounded-2xl hover:border-gold/30 transition-colors">
            <t.icon className="w-5 h-5 text-gold" />
            <div className="text-2xl font-bold text-white mt-3">{t.value}</div>
            <div className="text-gray-400 text-[11px] uppercase tracking-widest mt-1 font-bold">{t.label}</div>
          </Link>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
        {data?.queues.map((q) => <QueueCard key={q.key} q={q} />)}
      </div>
    </div>
  );
}
