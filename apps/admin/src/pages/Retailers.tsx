import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Edit2, Plus, Search, Trash2 } from 'lucide-react';
import type { RetailerIn, RetailerOut } from '@api-types';
import api, { errorMessage } from '../lib/api';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Button, Field, Modal, PageHeader, inputClass } from '../components/ui';

export default function Retailers() {
  const qc = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<RetailerOut | 'new' | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ['retailers'], queryFn: () => api.get<RetailerOut[]>('/prices/retailers').then((r) => r.data) });

  const save = useMutation({
    mutationFn: ({ id, body }: { id?: number; body: RetailerIn }) => (id ? api.put(`/prices/admin/retailers/${id}`, body) : api.post('/prices/admin/retailers', body)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['retailers'] });
      toast('Retailer saved');
      setEditing(null);
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });
  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/prices/admin/retailers/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['retailers'] });
      toast('Retailer deleted');
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const rows = (data ?? []).filter((r) => !search || r.name.toLowerCase().includes(search.toLowerCase()));
  const columns: Column<RetailerOut>[] = [
    {
      header: 'Retailer',
      cell: (r) => (
        <div>
          <div className="font-semibold text-white">{r.name}</div>
          {r.website_url && <div className="text-[11px] text-gold/70 truncate max-w-[260px]">{r.website_url}</div>}
        </div>
      ),
    },
    { header: 'Country', cell: (r) => r.country || <span className="text-gray-500">—</span> },
    {
      header: 'Actions',
      cell: (r) => (
        <div className="flex gap-1">
          <button onClick={() => setEditing(r)} className="p-1.5 text-gold hover:bg-gold/10 rounded" aria-label={`Edit ${r.name}`}>
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => confirm(`Delete “${r.name}” and all prices logged for it?`) && del.mutate(r.id)}
            className="p-1.5 text-red-300 hover:bg-red-400/10 rounded"
            aria-label={`Delete ${r.name}`}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retailers"
        subtitle="Where prices are spotted"
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus className="w-4 h-4" /> New retailer
          </Button>
        }
      />
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input className={`${inputClass} pl-11`} placeholder="Search retailers…" aria-label="Search retailers" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} isLoading={isLoading} />
      {editing && <RetailerModal row={editing === 'new' ? null : editing} saving={save.isPending} onClose={() => setEditing(null)} onSave={(body) => save.mutate({ id: editing === 'new' ? undefined : editing.id, body })} />}
    </div>
  );
}

function RetailerModal({ row, saving, onClose, onSave }: { row: RetailerOut | null; saving: boolean; onClose: () => void; onSave: (b: RetailerIn) => void }) {
  const { register, handleSubmit, formState } = useForm<RetailerIn>({ defaultValues: { name: row?.name ?? '', website_url: row?.website_url ?? '', country: row?.country ?? '' } });
  return (
    <Modal title={row ? 'Edit retailer' : 'New retailer'} onClose={onClose}>
      <form onSubmit={handleSubmit((v) => onSave({ name: v.name, website_url: v.website_url || null, country: v.country || null }))} className="space-y-4">
        <Field label="Name" required error={formState.errors.name && 'Name is required'}>
          <input {...register('name', { required: true })} className={inputClass} autoFocus />
        </Field>
        <Field label="Website">
          <input {...register('website_url')} type="url" className={inputClass} placeholder="https://…" />
        </Field>
        <Field label="Country">
          <input {...register('country')} className={inputClass} placeholder="e.g. RS, DE, US" />
        </Field>
        <div className="flex justify-end gap-3">
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
