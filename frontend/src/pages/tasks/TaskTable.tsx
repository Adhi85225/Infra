/**
 * T1 -- the task table, shared by the Task Updates page and every service page.
 *
 * One component covers both because they differ only in configuration:
 *
 *   <TaskTable />                     global: every user's tasks, no Action column
 *   <TaskTable service="DAS" />       one service, scoped by the API, Action column
 *
 * Filtering, searching, sorting and paging all happen on the server -- the
 * browser never holds more than one page of rows, and, more importantly, the
 * "whose tasks may I see" rule is the API's to enforce. Anything this component
 * does with `service` or `user_id` is a convenience for the reader, never a
 * security boundary: see `app/services/task_service.py`.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import { can, canManage, type PermissionMap } from '@/auth/permissions';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import {
  TASK_STATUSES,
  type Page,
  type Task,
  type TaskService,
  type TaskStatus,
  type User,
} from '@/lib/types';
import { TaskDialog } from './TaskDialog';
import { formatDate, rangeFor, type DateFilter } from './taskDates';

const PAGE_SIZE = 20;

/** Sortable columns, in display order. `null` marks a column that is not sortable. */
const COLUMNS: { key: string | null; label: string; className?: string }[] = [
  { key: null, label: 'Sl. No.', className: 'w-16' },
  { key: 'task_date', label: 'Date' },
  { key: 'reference_number', label: 'Case/WO/Jira' },
  { key: 'site_name', label: 'Site Name' },
  { key: 'description', label: 'Description/Subject' },
  { key: 'status', label: 'Status' },
  { key: 'remarks', label: 'Remarks' },
  { key: 'service', label: 'Service' },
  { key: 'user', label: 'User' },
];

const STATUS_TONES: Record<TaskStatus, 'neutral' | 'green' | 'amber' | 'red' | 'blue'> = {
  Created: 'blue',
  Inprogress: 'amber',
  Onhold: 'neutral',
  Completed: 'green',
  Triage: 'red',
};

function SortHeader({
  label,
  column,
  sortBy,
  direction,
  onSort,
  className,
}: {
  label: string;
  column: string | null;
  sortBy: string;
  direction: 'asc' | 'desc';
  onSort: (column: string) => void;
  className?: string;
}) {
  if (column === null) {
    return (
      <th scope="col" className={`px-4 py-3 font-semibold ${className ?? ''}`}>
        {label}
      </th>
    );
  }

  const active = sortBy === column;
  return (
    <th
      scope="col"
      aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={`px-4 py-3 font-semibold ${className ?? ''}`}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className="inline-flex items-center gap-1 font-semibold uppercase tracking-wide
                   text-slate-500 hover:text-slate-900"
      >
        {label}
        <span aria-hidden="true" className={active ? 'text-brand-600' : 'text-slate-300'}>
          {active ? (direction === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  );
}

export function TaskTable({
  service,
  permissionMap,
  initialStatus = '',
  initialDateFilter = 'all',
  initialCustomDate = '',
}: {
  /** Undefined renders the global Task Updates view. */
  service?: TaskService;
  permissionMap: PermissionMap;
  /** Opening filters, used when the dashboard drills through to a subset. */
  initialStatus?: TaskStatus | '';
  initialDateFilter?: DateFilter;
  initialCustomDate?: string;
}) {
  const { notify } = useToast();

  // Mirrors the API rule exactly: a task administrator is a caller holding
  // MANAGE on Access Management. Used only to decide what to render.
  const isTaskAdmin = canManage(permissionMap, 'ACCESS_MANAGEMENT');
  const canCreate = can(permissionMap, 'TASK_UPDATES', 'CREATE');
  const isServiceView = service !== undefined;

  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [dateFilter, setDateFilter] = useState<DateFilter>(initialDateFilter);
  const [customDate, setCustomDate] = useState(initialCustomDate);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | ''>(initialStatus);
  const [userFilter, setUserFilter] = useState('');
  const [sortBy, setSortBy] = useState('task_date');
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [assignees, setAssignees] = useState<User[]>([]);

  const query = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
      sort_by: sortBy,
      direction,
    });
    if (service) params.set('service', service);
    if (search.trim()) params.set('search', search.trim());
    if (statusFilter) params.set('status', statusFilter);
    // Only meaningful on a service page, and only honoured by the API for a
    // task administrator.
    if (isServiceView && isTaskAdmin && userFilter) params.set('user_id', userFilter);

    const range = rangeFor(dateFilter, customDate);
    if (range) {
      params.set('date_from', range.from);
      params.set('date_to', range.to);
    }
    return params.toString();
  }, [
    offset,
    sortBy,
    direction,
    service,
    search,
    statusFilter,
    isServiceView,
    isTaskAdmin,
    userFilter,
    dateFilter,
    customDate,
  ]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await api.get<Page<Task>>(`/tasks?${query}`);
      setTasks(page.items);
      setTotal(page.total);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load tasks.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  // Debounced so typing in the search box does not spam the API, matching the
  // behaviour of the user list.
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  // The assignee list drives the admin-only user filter and the User field in
  // the form. Fetched once, and only for callers who can read it.
  useEffect(() => {
    if (!isTaskAdmin) return;
    let cancelled = false;
    void api
      .get<Page<User>>('/users?limit=100')
      .then((page) => {
        if (!cancelled) setAssignees(page.items);
      })
      .catch(() => {
        /* the filter degrades to "All users"; the table still works */
      });
    return () => {
      cancelled = true;
    };
  }, [isTaskAdmin]);

  const onSort = useCallback(
    (column: string) => {
      setOffset(0);
      if (sortBy === column) {
        setDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortBy(column);
        // Dates read best newest-first; text reads best A-Z.
        setDirection(column === 'task_date' ? 'desc' : 'asc');
      }
    },
    [sortBy],
  );

  const closeCreate = useCallback(() => setCreating(false), []);
  const closeEdit = useCallback(() => setEditing(null), []);
  const afterSave = useCallback(
    (message: string) => {
      setCreating(false);
      setEditing(null);
      notify(message, 'success');
      void load();
    },
    [notify, load],
  );
  const afterCreate = useCallback(() => afterSave('Task added.'), [afterSave]);
  const afterEdit = useCallback(() => afterSave('Task updated.'), [afterSave]);

  const filtersApplied =
    search.trim() !== '' || dateFilter !== 'all' || statusFilter !== '' || userFilter !== '';

  const columns = isServiceView ? [...COLUMNS, { key: null, label: 'Action' }] : COLUMNS;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(event) => {
            setOffset(0);
            setSearch(event.target.value);
          }}
          placeholder="Search reference, site, description…"
          aria-label="Search tasks"
          className="field-input max-w-xs"
        />

        {/* Quick date filters */}
        <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5" role="group"
             aria-label="Filter by date">
          {(['all', 'today', 'yesterday', 'custom'] as DateFilter[]).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={dateFilter === option}
              onClick={() => {
                setOffset(0);
                setDateFilter(option);
              }}
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
            onChange={(event) => {
              setOffset(0);
              setCustomDate(event.target.value);
            }}
            aria-label="Choose a date"
            className="field-input max-w-[11rem]"
          />
        )}

        <select
          value={statusFilter}
          onChange={(event) => {
            setOffset(0);
            setStatusFilter(event.target.value as TaskStatus | '');
          }}
          aria-label="Filter by status"
          className="field-input max-w-[10rem]"
        >
          <option value="">All statuses</option>
          {TASK_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>

        {/* Administrators only, and only where rows span several users. */}
        {isServiceView && isTaskAdmin && (
          <select
            value={userFilter}
            onChange={(event) => {
              setOffset(0);
              setUserFilter(event.target.value);
            }}
            aria-label="Filter by user"
            className="field-input max-w-[14rem]"
          >
            <option value="">All users</option>
            {assignees.map((assignee) => (
              <option key={assignee.id} value={assignee.id}>
                {assignee.full_name}
              </option>
            ))}
          </select>
        )}

        <div className="ml-auto">
          {canCreate && <Button onClick={() => setCreating(true)}>Add task</Button>}
        </div>
      </div>

      {loading && tasks.length === 0 ? (
        <LoadingState label="Loading tasks…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No tasks found"
          description={
            filtersApplied
              ? 'No tasks match the current filters.'
              : isServiceView
                ? `No ${service} tasks have been recorded yet.`
                : 'No tasks have been recorded yet.'
          }
          action={canCreate ? <Button onClick={() => setCreating(true)}>Add task</Button> : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">
              {isServiceView ? `${service} tasks` : 'All task updates'}
            </caption>
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {columns.map((column) => (
                  <SortHeader
                    key={column.label}
                    label={column.label}
                    column={column.key}
                    sortBy={sortBy}
                    direction={direction}
                    onSort={onSort}
                    className={column.className}
                  />
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tasks.map((task, index) => (
                <tr key={task.id} className="hover:bg-slate-50">
                  {/* Position in the current result, so it keeps counting across pages. */}
                  <td className="px-4 py-3 text-slate-500">{offset + index + 1}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {formatDate(task.task_date)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {task.reference_number ?? <span className="text-slate-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {task.site_name ?? <span className="text-slate-400">—</span>}
                  </td>
                  <td className="max-w-md px-4 py-3">
                    <span className="font-medium text-slate-900">{task.description}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONES[task.status]}>{task.status}</Badge>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-slate-600">
                    {task.remarks ?? <span className="text-slate-400">—</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{task.service}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{task.user_name}</td>
                  {isServiceView && (
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      {task.can_edit ? (
                        <button
                          type="button"
                          onClick={() => setEditing(task)}
                          aria-label={`Edit task: ${task.description}`}
                          title="Edit task"
                          className="rounded p-1.5 text-slate-500 hover:bg-slate-100
                                     hover:text-brand-700"
                        >
                          <span aria-hidden="true">✎</span>
                        </button>
                      ) : (
                        <span className="text-slate-300" aria-hidden="true">
                          —
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <TaskDialog
        open={creating}
        service={service}
        assignees={assignees}
        canAssign={isTaskAdmin}
        onClose={closeCreate}
        onSaved={afterCreate}
      />

      <TaskDialog
        open={editing !== null}
        task={editing}
        service={service}
        assignees={assignees}
        canAssign={isTaskAdmin}
        onClose={closeEdit}
        onSaved={afterEdit}
      />
    </div>
  );
}
