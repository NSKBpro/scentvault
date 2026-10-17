import { useEffect, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Loader2, X } from 'lucide-react';
import clsx from 'clsx';

export const inputClass =
  'w-full bg-navy-dark border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-gold/50 focus:ring-1 focus:ring-gold/30 transition-colors placeholder:text-gray-500';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({
  variant = 'primary',
  loading,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'primary' && 'bg-gold text-navy hover:bg-gold-light shadow-lg shadow-gold/10',
        variant === 'secondary' && 'bg-navy-light border border-gold/30 text-gold hover:bg-gold/10',
        variant === 'ghost' && 'text-gray-300 hover:text-white hover:bg-white/5',
        variant === 'danger' && 'bg-red-500/10 border border-red-500/30 text-red-300 hover:bg-red-500/20',
        className,
      )}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between items-end gap-4">
      <div>
        <h1 className="text-2xl font-serif font-bold text-white">{title}</h1>
        {subtitle && <p className="text-gold/70 text-xs uppercase tracking-widest mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-3">{actions}</div>}
    </div>
  );
}

export function Field({ label, error, hint, required, children }: { label: string; error?: string; hint?: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[11px] font-bold text-gold uppercase tracking-wider ml-1">
        {label} {required && <span className="text-red-400">*</span>}
      </span>
      {children}
      {hint && !error && <span className="block text-xs text-gray-400 ml-1">{hint}</span>}
      {error && <span className="block text-xs text-red-300 ml-1 font-medium">{error}</span>}
    </label>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
        className={clsx('bg-navy border border-white/10 rounded-2xl w-full p-6 shadow-2xl max-h-[90vh] overflow-y-auto', wide ? 'max-w-2xl' : 'max-w-md')}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-serif text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Badge({ children, tone = 'gold' }: { children: ReactNode; tone?: 'gold' | 'green' | 'red' | 'gray' | 'blue' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide border',
        tone === 'gold' && 'bg-gold/10 text-gold border-gold/25',
        tone === 'green' && 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
        tone === 'red' && 'bg-red-500/10 text-red-300 border-red-500/25',
        tone === 'gray' && 'bg-white/5 text-gray-300 border-white/10',
        tone === 'blue' && 'bg-sky-500/10 text-sky-300 border-sky-500/25',
      )}
    >
      {children}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={clsx('bg-navy-light border border-white/[0.08] rounded-2xl p-6', className)}>{children}</section>;
}
