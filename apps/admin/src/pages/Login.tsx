import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import type { TokenPair } from '@api-types';
import api, { errorMessage } from '../lib/api';
import { saveSession } from '../lib/auth';
import { Button, Field, inputClass } from '../components/ui';

interface LoginForm {
  email: string;
  password: string;
}

export default function Login() {
  const { register, handleSubmit } = useForm<LoginForm>();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.post<TokenPair>('/auth/login/json', data);
      // The panel is admin-only: refuse other roles here instead of failing on the first admin call.
      if (res.data.user.role !== 'admin') {
        setError('This account is not an administrator. Ask an admin to grant access, or use the mobile app.');
        return;
      }
      saveSession(res.data);
      navigate('/');
    } catch (err) {
      setError(errorMessage(err, 'Invalid email or password'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-navy p-4 font-sans">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          <h1 className="text-5xl font-serif font-bold text-gold">ScentVault</h1>
          <p className="text-gray-400 uppercase tracking-[0.3em] text-xs mt-3">Admin sign in</p>
        </div>
        <div className="bg-navy-light border border-white/[0.08] rounded-2xl p-8 shadow-2xl shadow-black/50">
          {error && (
            <div role="alert" className="mb-6 p-4 bg-red-500/10 border border-red-500/25 text-red-200 rounded-xl text-sm">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <Field label="Email">
              <input {...register('email', { required: true })} type="email" autoComplete="email" className={inputClass} placeholder="admin@example.com" />
            </Field>
            <Field label="Password">
              <input {...register('password', { required: true })} type="password" autoComplete="current-password" className={inputClass} placeholder="••••••••" />
            </Field>
            <Button type="submit" loading={loading} className="w-full py-3.5">
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
