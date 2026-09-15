/**
 * An existing service module page, showing the tasks raised against it.
 *
 * Replaces {@link ModulePlaceholderPage} for the five service modules that now
 * have real content. It looks the module up by route from the permission map,
 * exactly as the placeholder does, so no route or navigation entry is added:
 * `/das-onboarding` keeps its own URL, name and sidebar position and simply has
 * something to show.
 */

import { useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { moduleForRoute } from '@/auth/permissions';
import { AccessBadge } from '@/components/ui/Badge';
import { serviceForModule } from '@/lib/types';
import { NotFoundPage } from './NotFoundPage';
import { ServiceTasks } from './tasks/ServiceTasks';

export function ServiceModulePage() {
  const { permissions, permissionMap } = useAuth();
  const location = useLocation();

  const module = moduleForRoute(permissions, location.pathname);
  if (!module) return <NotFoundPage />;

  const service = serviceForModule(module.module_key);
  if (!service) return <NotFoundPage />;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
            <span aria-hidden="true">{module.icon}</span>
            {module.module_name}
          </h2>
          <p className="mt-1 text-sm text-slate-500">{module.description}</p>
        </div>
        <AccessBadge level={module.access_level} />
      </header>

      <ServiceTasks service={service} permissionMap={permissionMap} />
    </div>
  );
}
