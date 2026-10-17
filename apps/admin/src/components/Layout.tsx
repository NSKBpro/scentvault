import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Cpu, Database, DollarSign, Droplets, History, LayoutDashboard, Layers, LogOut, Menu, Package, Palette,
  Store, Tags, Users, CalendarDays,
} from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';
import api from '../lib/api';
import { clearSession, getRefreshToken, getUser } from '../lib/auth';

const sections = [
  { title: 'Overview', items: [{ name: 'Work queue', href: '/', icon: LayoutDashboard }] },
  {
    title: 'Catalog',
    items: [
      { name: 'Fragrances', href: '/fragrances', icon: Droplets },
      { name: 'Brands', href: '/brands', icon: Tags },
      { name: 'Notes', href: '/notes', icon: Database },
      { name: 'Families', href: '/families', icon: Layers },
      { name: 'Accords', href: '/accords', icon: Palette },
      { name: 'Occasions', href: '/occasions', icon: CalendarDays },
      { name: 'Embeddings', href: '/embeddings', icon: Cpu },
    ],
  },
  {
    title: 'Prices',
    items: [
      { name: 'Price logger', href: '/price-logger', icon: DollarSign },
      { name: 'Price history', href: '/prices', icon: History },
      { name: 'Retailers', href: '/retailers', icon: Store },
    ],
  },
  {
    title: 'System',
    items: [
      { name: 'Users', href: '/users', icon: Users },
      { name: 'Import / export', href: '/bulk-import', icon: Package },
    ],
  },
];

export default function Layout() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const user = getUser();
  const label = user?.display_name || user?.email || 'Admin';

  const logout = async () => {
    const refresh = getRefreshToken();
    if (refresh) await api.post('/auth/logout', { refresh_token: refresh }).catch(() => undefined);
    clearSession();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-navy text-gray-200 font-sans">
      {open && <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-navy-dark border-r border-white/[0.08] transform transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex flex-col h-full">
          <div className="p-6">
            <div className="text-2xl font-serif font-bold text-gold tracking-tight">ScentVault</div>
            <p className="text-[11px] text-gray-400 uppercase tracking-[0.2em] mt-1">Control Center</p>
          </div>
          <nav className="flex-1 px-3 space-y-5 overflow-y-auto" aria-label="Main">
            {sections.map((s) => (
              <div key={s.title}>
                <div className="px-3 mb-1 text-[11px] uppercase tracking-widest text-gray-500 font-bold">{s.title}</div>
                {s.items.map((item) => (
                  <NavLink
                    key={item.href}
                    to={item.href}
                    end={item.href === '/'}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all',
                        isActive ? 'bg-gold/10 text-gold border border-gold/20' : 'text-gray-300 hover:bg-white/5 hover:text-white border border-transparent',
                      )
                    }
                  >
                    <item.icon className="w-4 h-4 mr-3" />
                    {item.name}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="p-3 border-t border-white/[0.08]">
            <button onClick={logout} className="flex items-center w-full px-3 py-2.5 text-sm font-medium text-red-300 hover:bg-red-400/10 rounded-xl">
              <LogOut className="w-4 h-4 mr-3" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="h-16 border-b border-white/[0.08] bg-navy/70 backdrop-blur-md flex items-center justify-between px-6 lg:px-8 sticky top-0 z-30">
          <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Open menu">
            <Menu className="w-6 h-6 text-gold" />
          </button>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-white">{label}</p>
              <p className="text-[11px] text-gold uppercase tracking-wider">{user?.role}</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold to-gold-dark flex items-center justify-center text-navy font-bold" aria-hidden>
              {label[0]?.toUpperCase()}
            </div>
          </div>
        </header>
        <main className="p-6 lg:p-8 max-w-[1400px]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
