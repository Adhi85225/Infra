/**
 * Task Updates -- the global view.
 *
 * Deliberately unscoped: every task is listed whoever owns it. The per-service
 * pages are the scoped views, and they are where editing happens.
 */

import { NavLink } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { SERVICE_SLUGS, TASK_SERVICES } from '@/lib/types';
import { TaskTable } from './tasks/TaskTable';

export function TaskUpdatesPage() {
  const { permissionMap } = useAuth();

  return (
    <div>
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Task Updates</h2>
        <p className="mt-1 text-sm text-slate-500">
          Every team member's task updates. Open a service below to work with just that
          service's tasks.
        </p>
      </header>

      <nav aria-label="Services" className="mb-5 flex flex-wrap gap-2">
        {TASK_SERVICES.map((service) => (
          <NavLink
            key={service}
            to={`/task-updates/${SERVICE_SLUGS[service]}`}
            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs
                       font-medium text-slate-600 transition-colors hover:border-brand-300
                       hover:bg-brand-50 hover:text-brand-700"
          >
            {service}
          </NavLink>
        ))}
      </nav>

      <TaskTable permissionMap={permissionMap} />
    </div>
  );
}
