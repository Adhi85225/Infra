/**
 * Application shell: sidebar navigation, header and content area.
 *
 * The navigation is generated from the permission map the server sent, so a
 * module the user cannot view is never rendered and a newly added module
 * appears without touching this file.
 */

import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { ACCESS_LABELS, accessibleModules } from '@/auth/permissions';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

function Initials({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
  return (
    <span
      aria-hidden="true"
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full
                 bg-brand-100 text-xs font-semibold text-brand-700"
    >
      {initials}
    </span>
  );
}

export function Layout() {
  const { user, permissions, permissionMap, logout } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  const visible = accessibleModules(permissions);

  const navigation = (
    <nav aria-label="Modules" className="flex flex-col gap-0.5 p-3">
      {visible.map((permission) => (
        <NavLink
          key={permission.module_key}
          to={permission.route}
          onClick={() => setNavOpen(false)}
          className={({ isActive }) =>
            `group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'bg-brand-50 font-semibold text-brand-800'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`
          }
        >
          <span aria-hidden="true" className="w-5 text-base leading-none">
            {permission.icon}
          </span>
          <span className="min-w-0 flex-1 truncate">{permission.module_name}</span>
          {!permission.is_implemented && (
            <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              soon
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );

  const currentModule = visible.find(
    (permission) =>
      location.pathname === permission.route ||
      location.pathname.startsWith(`${permission.route}/`),
  );

  return (
    <div className="min-h-screen lg:flex">
      {/* Sidebar -- a drawer on small screens, permanent from lg up. */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-slate-200
                    bg-white transition-transform lg:static lg:translate-x-0
                    ${navOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
          <span aria-hidden="true" className="text-lg">
            🌐
          </span>
          <span className="text-sm font-semibold text-slate-900">Global Infrastructure</span>
        </div>
        {navigation}
      </aside>

      {navOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/30 lg:hidden"
          aria-hidden="true"
          onClick={() => setNavOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b
                           border-slate-200 bg-white px-4">
          <button
            type="button"
            onClick={() => setNavOpen((open) => !open)}
            aria-label="Toggle navigation"
            aria-expanded={navOpen}
            className="rounded p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            ☰
          </button>

          <div className="min-w-0 flex-1">
            {currentModule && (
              <div className="flex items-center gap-2">
                <h1 className="truncate text-sm font-semibold text-slate-900">
                  {currentModule.module_name}
                </h1>
                {/* A visible indicator of the access the user actually holds. */}
                <Badge tone={currentModule.can_manage ? 'green' : 'amber'}>
                  {ACCESS_LABELS[currentModule.access_level]}
                </Badge>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-tight text-slate-900">
                {user?.full_name}
              </p>
              <p className="text-xs leading-tight text-slate-500">
                {user?.roles.map((role) => role.name).join(', ') || 'No roles'}
              </p>
            </div>
            {user && <Initials name={user.full_name} />}
            <Button variant="secondary" size="sm" onClick={() => void logout()}>
              Sign out
            </Button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <div className="mx-auto w-full max-w-6xl">
            <Outlet context={{ permissionMap }} />
          </div>
        </main>
      </div>
    </div>
  );
}
