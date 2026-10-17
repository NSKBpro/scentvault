import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Edit2, Plus, Search, Shield, Trash2, User as UserIcon } from 'lucide-react';
import type { AdminUserOut, Page } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { getUser } from '../lib/auth';
import { shortDate, useDebounce } from '../lib/hooks';
import DataTable, { type Column } from '../components/DataTable';
import { useToast } from '../lib/toast';
import { Badge, Button, Field, Modal, PageHeader, inputClass } from '../components/ui';

interface UserForm {
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  password: string;
}

export default function Users() {
  const qc = useQueryClient();
  const toast = useToast();
  const me = getUser();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUserOut | 'new' | null>(null);
  const debounced = useDebounce(search);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, debounced, role],
    queryFn: () => api.get<Page<AdminUserOut>>('/admin/users', { params: { page, size: 15, search: debounced || undefined, role: role || undefined } }).then((r) => r.data),
    placeholderData: (p) => p,
  });

  const save = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Partial<UserForm> }) => (id ? api.put(`/admin/users/${id}`, body) : api.post('/admin/users', body)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      toast('User saved');
      setEditing(null);
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.delete(`/admin/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      toast('User deleted');
    },
    onError: (e) => toast(errorMessage(e), 'error'),
  });

  const columns: Column<AdminUserOut>[] = [
    {
      header: 'User',
      cell: (u) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-navy-dark border border-white/10 flex items-center justify-center">
            {u.role === 'admin' ? <Shield className="w-4 h-4 text-gold" /> : <UserIcon className="w-4 h-4 text-gray-300" />}
          </div>
          <div>
            <div className="text-white font-medium">{u.display_name || '—'}</div>
            <div className="text-xs text-gray-400">{u.email}</div>
          </div>
        </div>
      ),
    },
    { header: 'Role', cell: (u) => <Badge tone={u.role === 'admin' ? 'gold' : 'gray'}>{u.role}</Badge> },
    { header: 'Bottles', cell: (u) => u.collection_count },
    { header: 'Joined', cell: (u) => shortDate(u.created_at) },
    {
      header: 'Actions',
      cell: (u) => (
        <div className="flex gap-1">
          <button onClick={() => setEditing(u)} className="p-1.5 text-gold hover:bg-gold/10 rounded" aria-label={`Edit ${u.email}`}>
            <Edit2 className="w-4 h-4" />
          </button>
          {u.id !== me?.id && (
            <button
              onClick={() => confirm(`Delete ${u.email}? Their collection, wears and alerts are deleted too.`) && del.mutate(u.id)}
              className="p-1.5 text-red-300 hover:bg-red-400/10 rounded"
              aria-label={`Delete ${u.email}`}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        subtitle={`${data?.total ?? 0} accounts`}
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus className="w-4 h-4" /> New user
          </Button>
        }
      />
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className={`${inputClass} pl-11`}
            placeholder="Search email or name…"
            aria-label="Search users"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <select aria-label="Role" className={`${inputClass} w-40`} value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
          <option value="">All roles</option>
          <option value="user">Users</option>
          <option value="admin">Admins</option>
        </select>
      </div>
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(u) => u.id} isLoading={isLoading} page={page} total={data?.total ?? 0} size={15} onPage={setPage} />
      {editing && (
        <UserModal
          user={editing === 'new' ? null : editing}
          saving={save.isPending}
          onClose={() => setEditing(null)}
          onSave={(v) => {
            const isNew = editing === 'new';
            const body: Partial<UserForm> = { display_name: v.display_name || undefined, role: v.role };
            // Only send the email when it changed, so an unusual legacy address never blocks other edits.
            if (isNew || v.email.trim().toLowerCase() !== editing.email) body.email = v.email.trim();
            if (v.password) body.password = v.password;
            save.mutate({ id: editing === 'new' ? undefined : editing.id, body });
          }}
        />
      )}
    </div>
  );
}

function UserModal({ user, saving, onClose, onSave }: { user: AdminUserOut | null; saving: boolean; onClose: () => void; onSave: (v: UserForm) => void }) {
  const { register, handleSubmit, formState } = useForm<UserForm>({
    defaultValues: { email: user?.email ?? '', display_name: user?.display_name ?? '', role: user?.role ?? 'user', password: '' },
  });
  return (
    <Modal title={user ? 'Edit user' : 'New user'} onClose={onClose}>
      <form onSubmit={handleSubmit(onSave)} className="space-y-4">
        <Field label="Email" required error={formState.errors.email && 'Email is required'}>
          <input {...register('email', { required: true })} type="email" className={inputClass} />
        </Field>
        <Field label="Display name">
          <input {...register('display_name')} className={inputClass} />
        </Field>
        <Field label="Role">
          <select {...register('role')} className={inputClass}>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </Field>
        <Field label={user ? 'New password' : 'Password'} required={!user} hint={user ? 'Leave empty to keep the current password' : 'At least 8 characters'} error={formState.errors.password && 'At least 8 characters'}>
          <input {...register('password', { required: !user, minLength: 8 })} type="password" autoComplete="new-password" className={inputClass} />
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
