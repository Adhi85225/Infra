/**
 * Task Updates -- the cross-service view.
 *
 * Deliberately unscoped: every task is listed whoever owns it and whatever
 * service it belongs to. Per-service views are not here — each existing service
 * page (DAS Onboarding, Zabbix, ...) renders the same T1 table filtered to its
 * own service, so this module never duplicates the application's navigation.
 */

import { useSearchParams } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { TASK_STATUSES, type TaskStatus } from '@/lib/types';
import type { DateFilter } from './tasks/taskDates';
import { TaskTable } from './tasks/TaskTable';

const DATE_FILTERS: DateFilter[] = ['all', 'today', 'yesterday', 'custom'];

export function TaskUpdatesPage() {
  const { permissionMap } = useAuth();
  const [params] = useSearchParams();

  // Drill-downs from the dashboard arrive as query parameters. Anything
  // unrecognised is ignored rather than passed through to the API.
  const status = params.get('status');
  const date = params.get('date');
  const initialStatus = TASK_STATUSES.includes(status as TaskStatus) ? (status as TaskStatus) : '';
  const initialDateFilter = DATE_FILTERS.includes(date as DateFilter)
    ? (date as DateFilter)
    : 'all';

  return (
    <div>
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Task Updates</h2>
        <p className="mt-1 text-sm text-slate-500">
          Every team member's task updates, across all services. Each service's own page
          shows just its tasks.
        </p>
      </header>

      <TaskTable
        permissionMap={permissionMap}
        initialStatus={initialStatus}
        initialDateFilter={initialDateFilter}
        initialCustomDate={params.get('on') ?? ''}
      />
    </div>
  );
}
