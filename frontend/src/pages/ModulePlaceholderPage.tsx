import { Link, useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { moduleForRoute } from '@/auth/permissions';
import { AccessBadge } from '@/components/ui/Badge';
import { NotFoundPage } from './NotFoundPage';

/**
 * One component serves every not-yet-built tool.
 *
 * Because it looks the module up by route from the permission map, adding a
 * module to the backend registry gives it a working, access-controlled page
 * with no frontend change at all.
 */
export function ModulePlaceholderPage() {
  const { permissions } = useAuth();
  const location = useLocation();

  const module = moduleForRoute(permissions, location.pathname);
  if (!module) return <NotFoundPage />;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
        <div aria-hidden="true" className="text-4xl">
          {module.icon}
        </div>
        <h2 className="mt-3 text-lg font-semibold text-slate-900">{module.module_name}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{module.description}</p>

        <div className="mt-4 flex items-center justify-center gap-2">
          <span className="text-xs text-slate-500">Your access:</span>
          <AccessBadge level={module.access_level} />
        </div>

        <div className="mt-6 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-5">
          <p className="text-sm font-medium text-slate-700">This tool is not built yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Phase 1 delivers the authentication and access foundation. This module is a
            placeholder; its functionality arrives in a later phase.
          </p>
        </div>

        <Link
          to="/dashboard"
          className="mt-6 inline-block text-sm font-medium text-brand-700 hover:underline"
        >
          ← Back to dashboard
        </Link>
      </div>
    </div>
  );
}
