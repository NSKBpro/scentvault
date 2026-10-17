import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
  sortKey?: string;
  className?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  isLoading?: boolean;
  empty?: ReactNode;
  sort?: string;
  onSort?: (key: string) => void;
  page?: number;
  total?: number;
  size?: number;
  onPage?: (page: number) => void;
  onRowClick?: (row: T) => void;
}

export default function DataTable<T>({ columns, rows, rowKey, isLoading, empty, sort, onSort, page, total, size, onPage, onRowClick }: Props<T>) {
  const totalPages = total != null && size ? Math.max(1, Math.ceil(total / size)) : 1;
  return (
    <div className="bg-navy-light border border-white/[0.08] rounded-2xl overflow-hidden shadow-xl">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/[0.08]">
          <thead className="bg-navy-dark">
            <tr>
              {columns.map((col) => {
                const active = sort === col.sortKey;
                return (
                  <th key={col.header} scope="col" className={clsx('px-5 py-3.5 text-left text-[11px] font-bold text-gold uppercase tracking-widest', col.className)}>
                    {col.sortKey && onSort ? (
                      <button onClick={() => onSort(col.sortKey!)} className="inline-flex items-center gap-1 hover:text-gold-light" aria-label={`Sort by ${col.header}`}>
                        {col.header}
                        {active ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3 opacity-30" />}
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.06]">
            {isLoading &&
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={`sk-${i}`}>
                  {columns.map((c) => (
                    <td key={c.header} className="px-5 py-4">
                      <div className="h-4 rounded bg-white/[0.06] animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-5 py-12 text-center text-gray-400">
                  {empty ?? 'No records found.'}
                </td>
              </tr>
            )}
            {!isLoading &&
              rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={clsx('hover:bg-white/[0.03] transition-colors', onRowClick && 'cursor-pointer')}
                >
                  {columns.map((col) => (
                    <td key={col.header} className={clsx('px-5 py-3.5 text-sm text-gray-200 whitespace-nowrap', col.className)}>
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {onPage && page != null && total != null && (
        <div className="px-5 py-3 border-t border-white/[0.08] flex items-center justify-between bg-navy-dark/50">
          <div className="text-xs text-gray-400">
            Page <span className="font-bold text-white">{page}</span> of <span className="font-bold text-white">{totalPages}</span> · {total} total
          </div>
          <div className="flex gap-1">
            <button onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page" className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-30 text-gray-200">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => onPage(page + 1)} disabled={page >= totalPages} aria-label="Next page" className="p-2 rounded-lg hover:bg-white/5 disabled:opacity-30 text-gray-200">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
