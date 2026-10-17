import { useCallback, useState, type ReactNode } from 'react';
import { AlertCircle, Check, Info, X } from 'lucide-react';
import clsx from 'clsx';
import { ToastContext, type Kind } from '../lib/toast';

interface Toast {
  id: number;
  message: string;
  kind: Kind;
}


export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (message: string, kind: Kind = 'success') => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t.slice(-3), { id, message, kind }]);
      setTimeout(() => dismiss(id), kind === 'error' ? 6000 : 3500);
    },
    [dismiss],
  );
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="fixed top-5 right-5 z-[100] flex flex-col gap-2 w-[min(420px,calc(100vw-2.5rem))]" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className={clsx(
              'flex items-start gap-3 px-4 py-3 rounded-xl shadow-2xl text-sm font-medium border',
              t.kind === 'success' && 'bg-emerald-950/95 border-emerald-500/30 text-emerald-200',
              t.kind === 'error' && 'bg-red-950/95 border-red-500/30 text-red-200',
              t.kind === 'info' && 'bg-navy-light/95 border-gold/30 text-gray-100',
            )}
          >
            {t.kind === 'success' ? <Check className="w-4 h-4 mt-0.5 shrink-0" /> : t.kind === 'error' ? <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> : <Info className="w-4 h-4 mt-0.5 shrink-0" />}
            <span className="flex-1">{t.message}</span>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="opacity-60 hover:opacity-100">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

