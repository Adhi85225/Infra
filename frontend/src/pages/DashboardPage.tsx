import { Link } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { accessibleModules } from '@/auth/permissions';
import { AccessBadge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/States';
import type { Permission } from '@/lib/types';

/**
 * Cards are generated from the server's effective permission map.
 *
 * Only modules the user can actually reach are shown -- a tool they have no
 * access to is not advertised at all. The API enforces the same rule, so hiding
 * a card is presentation, never the security boundary.
 */
function ModuleCard({ permission }: { permission: Permission }) {
  return (
    <Link
      to={permission.route}
      aria-label={`${permission.module_name} — ${permission.access_level.replace('_', ' ').toLowerCase()}`}
      className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 text-left
                 transition-shadow hover:border-brand-300 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <span aria-hidden="true" className="text-2xl leading-none">
          {permission.icon}
        </span>
        <AccessBadge level={permission.access_level} />
      </div>

      <div className="mt-3">
        <p className="font-semibold text-slate-900">{permission.module_name}</p>
        <p className="mt-1 line-clamp-2 text-sm text-slate-500">{permission.description}</p>
      </div>

      {!permission.is_implemented && (
        <div className="mt-3">
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold
                           uppercase tracking-wide text-slate-500">
            Coming soon
          </span>
        </div>
      )}
    </Link>
  );
}

export function DashboardPage() {
  const { user, permissions } = useAuth();

  // Effective access across every assigned role, resolved server-side.
  const modules = accessibleModules(permissions).filter(
    (permission) => permission.module_key !== 'DASHBOARD',
  );

  return (
    <div>
      <header className="mb-6">
        <h2 className="text-xl font-semibold text-slate-900">
          Welcome back, {user?.first_name}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {modules.length === 0
            ? 'No tools are available to you yet.'
            : `You have access to ${modules.length} ${modules.length === 1 ? 'tool' : 'tools'}.`}
          {user?.roles.length
            ? ` Signed in as ${user.roles.map((role) => role.name).join(', ')}.`
            : ''}
        </p>
      </header>

      {modules.length === 0 ? (
        <EmptyState
          title="No tools available"
          description="Your roles do not grant access to any tools yet. Contact an administrator."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {modules.map((permission) => (
            <ModuleCard key={permission.module_key} permission={permission} />
          ))}
        </div>
      )}
    </div>
  );
}
