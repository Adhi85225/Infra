import { useMemo } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { accessibleModules, canView, toPermissionMap } from '@/auth/permissions';
import { EmptyState } from '@/components/ui/States';
import { TaskAnalytics } from './dashboard/TaskAnalytics';

/**
 * The dashboard is the task overview.
 *
 * It used to open with a grid of module cards, but that listed the same tools
 * as the sidebar and, once the analytics arrived, the same services as the
 * quick-access cards at the bottom -- three routes to the same places above the
 * fold. The grid is gone; navigation belongs to the sidebar, and the space
 * belongs to the figures.
 */
export function DashboardPage() {
  const { user, permissions } = useAuth();

  // Derived from `permissions` rather than taken separately from the context,
  // so everything below agrees about access.
  const permissionMap = useMemo(() => toPermissionMap(permissions), [permissions]);

  const modules = accessibleModules(permissions).filter(
    (permission) => permission.module_key !== 'DASHBOARD',
  );
  const showAnalytics = canView(permissionMap, 'TASK_UPDATES');

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

      {showAnalytics ? (
        <TaskAnalytics permissionMap={permissionMap} permissions={permissions} />
      ) : (
        <EmptyState
          title={modules.length === 0 ? 'No tools available' : 'Nothing to show here'}
          description={
            modules.length === 0
              ? 'Your roles do not grant access to any tools yet. Contact an administrator.'
              : 'Your tools are listed in the sidebar. Task Updates is not available to you, so there are no figures to show.'
          }
        />
      )}
    </div>
  );
}
