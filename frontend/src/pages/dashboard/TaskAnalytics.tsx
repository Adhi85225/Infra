/**
 * Task analytics for the dashboard.
 *
 * Added alongside the existing module grid rather than replacing it.
 *
 * One filter state drives everything, and one request answers it: the API
 * aggregates in PostgreSQL and returns counts, the trend and the recent rows
 * together (`GET /tasks/analytics`). No widget fetches for itself, so the
 * charts cannot disagree about which filters are applied, and the browser never
 * downloads task rows in order to count them.
 *
 * Every drill-down lands on a page that already exists: a service bar or card
 * opens that service's own module page, a status opens Task Updates filtered.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { canManage, type PermissionMap } from '@/auth/permissions';
import { Button } from '@/components/ui/Button';
import { BarChart } from '@/components/ui/charts/BarChart';
import { DonutChart } from '@/components/ui/charts/DonutChart';
import { LineChart } from '@/components/ui/charts/LineChart';
import { STATUS_COLORS } from '@/components/ui/charts/palette';
import { ErrorState, Spinner } from '@/components/ui/States';
import { ApiError, api } from '@/lib/api';
import {
  TASK_SERVICES,
  TASK_STATUSES,
  type Page,
  type Permission,
  type TaskAnalytics as Analytics,
  type TaskService,
  type TaskStatus,
  type User,
} from '@/lib/types';
import { formatDate, rangeFor, type DateFilter } from '@/pages/tasks/taskDates';

/** A panel, matching the card treatment the dashboard already uses. */
function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={title} className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function KpiCard({
  label,
  value,
  accent,
  loading,
  onClick,
}: {
  label: string;
  value: number;
  accent?: string;
  loading: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <div className="flex items-center gap-2">
        {accent && (
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: accent }} />
        )}
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      </div>
      <span className="mt-2 block text-2xl font-semibold tabular-nums text-slate-900">
        {loading ? <span className="inline-block h-7 w-10 animate-pulse rounded bg-slate-100" /> : value}
      </span>
    </>
  );

  const shell =
    'rounded-lg border border-slate-200 bg-white p-4 text-left transition-shadow';

  return onClick ? (
    <button type="button" onClick={onClick} className={`${shell} hover:border-brand-300 hover:shadow-md`}>
      {body}
    </button>
  ) : (
    <div className={shell}>{body}</div>
  );
}

export function TaskAnalytics({
  permissionMap,
  permissions,
}: {
  permissionMap: PermissionMap;
  permissions: Permission[];
}) {
  const navigate = useNavigate();
  const isTaskAdmin = canManage(permissionMap, 'ACCESS_MANAGEMENT');

  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [customDate, setCustomDate] = useState('');
  const [service, setService] = useState<TaskService | ''>('');
  const [status, setStatus] = useState<TaskStatus | ''>('');
  const [userId, setUserId] = useState('');

  const [data, setData] = useState<Analytics | null>(null);
  const [assignees, setAssignees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (service) params.set('service', service);
    if (status) params.set('status', status);
    if (isTaskAdmin && userId) params.set('user_id', userId);
    const range = rangeFor(dateFilter, customDate);
    if (range) {
      params.set('date_from', range.from);
      params.set('date_to', range.to);
    }
    return params.toString();
  }, [service, status, isTaskAdmin, userId, dateFilter, customDate]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<Analytics>(`/tasks/analytics${query ? `?${query}` : ''}`));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load task analytics.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  // Only administrators can act on a user filter, so only they fetch the list.
  useEffect(() => {
    if (!isTaskAdmin) return;
    let cancelled = false;
    void api
      .get<Page<User>>('/users?limit=100')
      .then((page) => {
        if (!cancelled) setAssignees(page.items);
      })
      .catch(() => {
        /* the filter degrades to "All users"; the analytics still render */
      });
    return () => {
      cancelled = true;
    };
  }, [isTaskAdmin]);

  /** The existing route that owns a service, or undefined if unreachable. */
  const routeForModule = useCallback(
    (moduleKey: string): string | undefined => {
      const permission = permissions.find((entry) => entry.module_key === moduleKey);
      return permission?.can_view ? permission.route : undefined;
    },
    [permissions],
  );

  /** Task Updates, carrying the current drill-down as query parameters. */
  const openTasks = useCallback(
    (extra: Record<string, string> = {}) => {
      const params = new URLSearchParams(extra);
      if (dateFilter !== 'all') {
        params.set('date', dateFilter);
        if (dateFilter === 'custom' && customDate) params.set('on', customDate);
      }
      const search = params.toString();
      navigate(`/task-updates${search ? `?${search}` : ''}`);
    },
    [navigate, dateFilter, customDate],
  );

  const counts = useMemo(() => {
    const byStatus = new Map((data?.by_status ?? []).map((entry) => [entry.status, entry.count]));
    return (value: TaskStatus) => byStatus.get(value) ?? 0;
  }, [data]);

  const filtersApplied = dateFilter !== 'all' || service !== '' || status !== '' || userId !== '';

  return (
    <section className="mt-8" aria-labelledby="task-analytics-heading">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 id="task-analytics-heading" className="text-lg font-semibold text-slate-900">
          Task analytics
        </h2>
        {loading && data !== null && <Spinner label="Refreshing" />}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5"
               role="group" aria-label="Filter by date">
            {(['all', 'today', 'yesterday', 'custom'] as DateFilter[]).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={dateFilter === option}
                onClick={() => setDateFilter(option)}
                className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                  dateFilter === option
                    ? 'bg-brand-600 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {option === 'all' ? 'All dates' : option === 'custom' ? 'Custom' : option}
              </button>
            ))}
          </div>

          {dateFilter === 'custom' && (
            <input
              type="date"
              value={customDate}
              onChange={(event) => setCustomDate(event.target.value)}
              aria-label="Choose a date"
              className="field-input max-w-[10.5rem] py-1 text-xs"
            />
          )}

          <select
            value={service}
            onChange={(event) => setService(event.target.value as TaskService | '')}
            aria-label="Filter by service"
            className="field-input max-w-[11rem] py-1 text-xs"
          >
            <option value="">All services</option>
            {TASK_SERVICES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>

          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as TaskStatus | '')}
            aria-label="Filter by status"
            className="field-input max-w-[10rem] py-1 text-xs"
          >
            <option value="">All statuses</option>
            {TASK_STATUSES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>

          {isTaskAdmin && (
            <select
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              aria-label="Filter by user"
              className="field-input max-w-[12rem] py-1 text-xs"
            >
              <option value="">All users</option>
              {assignees.map((assignee) => (
                <option key={assignee.id} value={assignee.id}>{assignee.full_name}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : (
        <div className="flex flex-col gap-4">
          {/* KPI cards */}
          <div
            role="group"
            aria-label="Task summary"
            className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
          >
            <KpiCard
              label="Total tasks"
              value={data?.total ?? 0}
              loading={loading && data === null}
              onClick={() => openTasks()}
            />
            {TASK_STATUSES.map((value) => (
              <KpiCard
                key={value}
                label={value}
                accent={STATUS_COLORS[value]}
                value={counts(value)}
                loading={loading && data === null}
                onClick={() => openTasks({ status: value })}
              />
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Tasks by service">
              <BarChart
                emptyLabel={
                  filtersApplied
                    ? 'No tasks match the selected filters.'
                    : 'No task data available yet.'
                }
                data={(data?.by_service ?? []).map((entry) => {
                  const route = routeForModule(entry.module_key);
                  return {
                    label: entry.service,
                    value: entry.count,
                    title: `${entry.service}: ${entry.count} task${entry.count === 1 ? '' : 's'}${
                      route ? ' — open this service' : ''
                    }`,
                    // Straight to the service's own existing page.
                    onClick: route ? () => navigate(route) : undefined,
                  };
                })}
              />
            </Panel>

            <Panel title="Tasks by status">
              <DonutChart
                centerLabel="Total tasks"
                emptyLabel={
                  filtersApplied
                    ? 'No tasks match the selected filters.'
                    : 'No task data available yet.'
                }
                slices={TASK_STATUSES.map((value) => ({
                  label: value,
                  value: counts(value),
                  color: STATUS_COLORS[value],
                  onClick: () => openTasks({ status: value }),
                }))}
              />
            </Panel>
          </div>

          <Panel
            title="Task activity over time"
            action={
              data && (
                <span className="text-xs text-slate-500">
                  {formatDate(data.trend_from)} – {formatDate(data.trend_to)}
                </span>
              )
            }
          >
            <LineChart
              points={data?.trend ?? []}
              emptyLabel={
                filtersApplied
                  ? 'No activity in this period for the selected filters.'
                  : 'No task activity recorded yet.'
              }
            />
          </Panel>

          <Panel
            title="Recent tasks"
            action={
              <Link to="/task-updates" className="text-xs font-medium text-brand-700 hover:underline">
                View all tasks →
              </Link>
            }
          >
            {(data?.recent.length ?? 0) === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                No task data available for the selected filters.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th scope="col" className="py-2 pr-4 font-semibold">Date</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Reference</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Site</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Description/Subject</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Status</th>
                      <th scope="col" className="py-2 pr-4 font-semibold">Service</th>
                      <th scope="col" className="py-2 font-semibold">User</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data?.recent.map((task) => (
                      <tr key={task.id}>
                        <td className="whitespace-nowrap py-2 pr-4 text-slate-600">
                          {formatDate(task.task_date)}
                        </td>
                        <td className="whitespace-nowrap py-2 pr-4 text-slate-600">
                          {task.reference_number ?? '—'}
                        </td>
                        <td className="py-2 pr-4 text-slate-600">{task.site_name ?? '—'}</td>
                        <td className="max-w-xs truncate py-2 pr-4 font-medium text-slate-900">
                          {task.description}
                        </td>
                        <td className="whitespace-nowrap py-2 pr-4">
                          <span className="inline-flex items-center gap-1.5 text-slate-700">
                            <span aria-hidden="true" className="h-2 w-2 rounded-full"
                                  style={{ backgroundColor: STATUS_COLORS[task.status] }} />
                            {task.status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap py-2 pr-4 text-slate-600">{task.service}</td>
                        <td className="whitespace-nowrap py-2 text-slate-600">{task.user_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Quick access to the existing service pages. */}
          <Panel title="Services">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {(data?.by_service ?? TASK_SERVICES.map((s) => ({ service: s, module_key: '', count: 0 })))
                .map((entry) => {
                  const route = routeForModule(entry.module_key);
                  const inner = (
                    <>
                      <p className="truncate text-sm font-semibold text-slate-900">{entry.service}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {entry.count} task{entry.count === 1 ? '' : 's'}
                      </p>
                      {route && (
                        <span className="mt-2 inline-block text-xs font-medium text-brand-700">
                          View tasks →
                        </span>
                      )}
                    </>
                  );
                  return route ? (
                    <Link
                      key={entry.service}
                      to={route}
                      className="rounded-lg border border-slate-200 bg-white p-3 transition-shadow
                                 hover:border-brand-300 hover:shadow-md"
                    >
                      {inner}
                    </Link>
                  ) : (
                    <div
                      key={entry.service}
                      title="You do not have access to this service"
                      className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 opacity-70"
                    >
                      {inner}
                    </div>
                  );
                })}
            </div>
          </Panel>

          <div className="flex justify-center">
            <Button variant="secondary" size="sm" onClick={() => openTasks()}>
              Open Task Updates
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
