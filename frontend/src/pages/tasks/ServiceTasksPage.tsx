/**
 * A single service's tasks.
 *
 * All six service pages are this one component: the service comes from the URL
 * and is handed to T1 as a filter, so the table exists once rather than six
 * times. Which rows actually come back is the API's decision, not this page's.
 */

import { NavLink, useParams } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { canManage } from '@/auth/permissions';
import { Alert } from '@/components/ui/Alert';
import { SERVICE_SLUGS, TASK_SERVICES, serviceFromSlug } from '@/lib/types';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { TaskTable } from './TaskTable';

export function ServiceTasksPage() {
  const { serviceSlug } = useParams<{ serviceSlug: string }>();
  const { permissionMap } = useAuth();
  const service = serviceFromSlug(serviceSlug);

  if (!service) return <NotFoundPage />;

  const isTaskAdmin = canManage(permissionMap, 'ACCESS_MANAGEMENT');

  return (
    <div>
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">{service}</h2>
        <p className="mt-1 text-sm text-slate-500">
          {isTaskAdmin
            ? `All ${service} tasks. Use the user filter to focus on one person.`
            : `Your ${service} tasks.`}
        </p>
      </header>

      <nav aria-label="Services" className="mb-5 flex flex-wrap gap-2">
        <NavLink
          to="/task-updates"
          className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs
                     font-medium text-slate-600 transition-colors hover:border-brand-300
                     hover:bg-brand-50 hover:text-brand-700"
        >
          All tasks
        </NavLink>
        {TASK_SERVICES.map((option) => (
          <NavLink
            key={option}
            to={`/task-updates/${SERVICE_SLUGS[option]}`}
            className={({ isActive }) =>
              `rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                isActive
                  ? 'border-brand-300 bg-brand-50 text-brand-700'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700'
              }`
            }
          >
            {option}
          </NavLink>
        ))}
      </nav>

      {!isTaskAdmin && (
        <div className="mb-4">
          <Alert tone="info">
            You are seeing your own {service} tasks. The Task Updates page lists everyone's.
          </Alert>
        </div>
      )}

      <TaskTable service={service} permissionMap={permissionMap} />
    </div>
  );
}
