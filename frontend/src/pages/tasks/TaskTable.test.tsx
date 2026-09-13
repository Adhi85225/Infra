/**
 * T1: columns, the service/global split, sorting, date filters, search and the
 * administrator-only user filter.
 *
 * The assertions are mostly about *what the table asks the API for*, because
 * filtering and scoping are server-side by design.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { PermissionMap } from '@/auth/permissions';
import { ToastProvider } from '@/components/ui/Toast';
import type { AccessLevel, Task } from '@/lib/types';
import { TaskTable } from './TaskTable';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const { api } = await import('@/lib/api');

function permission(moduleKey: string, level: AccessLevel) {
  return {
    module_key: moduleKey,
    module_name: moduleKey,
    icon: null,
    route: `/${moduleKey.toLowerCase()}`,
    description: null,
    sort_order: 10,
    is_implemented: true,
    access_level: level,
    can_view: level !== 'NONE',
    can_manage: level === 'COMPLETE',
  };
}

/** A normal user: may file their own tasks, but is not a task administrator. */
const USER_PERMISSIONS: PermissionMap = {
  TASK_UPDATES: permission('TASK_UPDATES', 'COMPLETE'),
  ACCESS_MANAGEMENT: permission('ACCESS_MANAGEMENT', 'READ_ONLY'),
};

/** An administrator: MANAGE on Access Management makes them a task admin. */
const ADMIN_PERMISSIONS: PermissionMap = {
  TASK_UPDATES: permission('TASK_UPDATES', 'COMPLETE'),
  ACCESS_MANAGEMENT: permission('ACCESS_MANAGEMENT', 'COMPLETE'),
};

function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    task_date: '2026-09-10',
    reference_number: 'INC-1024',
    site_name: 'Chennai DC',
    description: 'Replaced a failed disk',
    status: 'Inprogress',
    remarks: 'Waiting on vendor',
    service: 'DAS',
    user_id: 'user-1',
    user_name: 'Normal User',
    user_email: 'user@test.internal',
    created_at: '2026-09-10T00:00:00Z',
    updated_at: '2026-09-10T00:00:00Z',
    can_edit: true,
    ...overrides,
  };
}

function mockTasks(items: Task[]) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith('/users')) {
      return Promise.resolve({ items: [{ id: 'user-2', full_name: 'Other User' }], total: 1, limit: 100, offset: 0 });
    }
    return Promise.resolve({ items, total: items.length, limit: 20, offset: 0 });
  });
}

/** Query string of the most recent `/tasks` request. */
function lastTaskQuery(): URLSearchParams {
  const calls = vi.mocked(api.get).mock.calls.filter(([path]) => String(path).startsWith('/tasks'));
  return new URLSearchParams(String(calls[calls.length - 1]![0]).split('?')[1] ?? '');
}

function renderTable(props: Partial<React.ComponentProps<typeof TaskTable>> = {}) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <TaskTable permissionMap={USER_PERMISSIONS} {...props} />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe('TaskTable', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    mockTasks([task()]);
  });

  it('renders the T1 columns', async () => {
    renderTable();
    await screen.findByText('Replaced a failed disk');

    const headers = screen.getAllByRole('columnheader').map((cell) => cell.textContent?.trim());
    expect(headers).toEqual([
      'Sl. No.',
      expect.stringContaining('Date'),
      expect.stringContaining('Case/WO/Jira'),
      expect.stringContaining('Site Name'),
      expect.stringContaining('Description/Subject'),
      expect.stringContaining('Status'),
      expect.stringContaining('Remarks'),
      expect.stringContaining('Service'),
      expect.stringContaining('User'),
    ]);
  });

  it('numbers rows sequentially', async () => {
    mockTasks([task({ id: 'a' }), task({ id: 'b' }), task({ id: 'c' })]);
    renderTable();
    await screen.findAllByText('Replaced a failed disk');

    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[0]!.textContent)).toEqual([
      '1',
      '2',
      '3',
    ]);
  });

  it('defaults to newest first', async () => {
    renderTable();
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    const query = lastTaskQuery();
    expect(query.get('sort_by')).toBe('task_date');
    expect(query.get('direction')).toBe('desc');
  });

  it('has no Action column on the global view', async () => {
    renderTable();
    await screen.findByText('Replaced a failed disk');
    expect(screen.queryByRole('columnheader', { name: 'Action' })).not.toBeInTheDocument();
  });

  it('adds an Action column with an edit control on a service view', async () => {
    renderTable({ service: 'DAS' });
    await screen.findByText('Replaced a failed disk');

    expect(screen.getByRole('columnheader', { name: 'Action' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Edit task: Replaced a failed disk' }),
    ).toBeInTheDocument();
  });

  it('shows no edit control for a row the API marked read-only', async () => {
    mockTasks([task({ can_edit: false })]);
    renderTable({ service: 'DAS' });
    await screen.findByText('Replaced a failed disk');

    expect(
      screen.queryByRole('button', { name: /^Edit task:/ }),
    ).not.toBeInTheDocument();
  });

  it('filters by service on a service view', async () => {
    renderTable({ service: 'Nexus' });
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(lastTaskQuery().get('service')).toBe('Nexus');
  });

  it('sends no service filter on the global view', async () => {
    renderTable();
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(lastTaskQuery().has('service')).toBe(false);
  });

  it('sorts by a column when its header is clicked, toggling direction', async () => {
    const user = userEvent.setup();
    renderTable();
    await screen.findByText('Replaced a failed disk');

    await user.click(screen.getByRole('button', { name: /Site Name/ }));
    await waitFor(() => expect(lastTaskQuery().get('sort_by')).toBe('site_name'));
    expect(lastTaskQuery().get('direction')).toBe('asc');

    await user.click(screen.getByRole('button', { name: /Site Name/ }));
    await waitFor(() => expect(lastTaskQuery().get('direction')).toBe('desc'));
  });

  it('requests a single day for the Today filter', async () => {
    const user = userEvent.setup();
    renderTable();
    await screen.findByText('Replaced a failed disk');

    await user.click(screen.getByRole('button', { name: 'today' }));

    const expected = new Date();
    const iso = `${expected.getFullYear()}-${String(expected.getMonth() + 1).padStart(2, '0')}-${String(expected.getDate()).padStart(2, '0')}`;
    await waitFor(() => expect(lastTaskQuery().get('date_from')).toBe(iso));
    expect(lastTaskQuery().get('date_to')).toBe(iso);
  });

  it('requests the previous day for the Yesterday filter', async () => {
    const user = userEvent.setup();
    renderTable();
    await screen.findByText('Replaced a failed disk');

    await user.click(screen.getByRole('button', { name: 'yesterday' }));

    const expected = new Date();
    expected.setDate(expected.getDate() - 1);
    const iso = `${expected.getFullYear()}-${String(expected.getMonth() + 1).padStart(2, '0')}-${String(expected.getDate()).padStart(2, '0')}`;
    await waitFor(() => expect(lastTaskQuery().get('date_from')).toBe(iso));
  });

  it('requests the chosen day for a custom date', async () => {
    const user = userEvent.setup();
    renderTable();
    await screen.findByText('Replaced a failed disk');

    await user.click(screen.getByRole('button', { name: 'Custom' }));
    await user.type(screen.getByLabelText('Choose a date'), '2026-01-15');

    await waitFor(() => expect(lastTaskQuery().get('date_from')).toBe('2026-01-15'));
    expect(lastTaskQuery().get('date_to')).toBe('2026-01-15');
  });

  it('sends the search term to the API', async () => {
    const user = userEvent.setup();
    renderTable();
    await screen.findByText('Replaced a failed disk');

    await user.type(screen.getByLabelText('Search tasks'), 'disk');
    await waitFor(() => expect(lastTaskQuery().get('search')).toBe('disk'));
  });

  it('hides the user filter from a normal user', async () => {
    renderTable({ service: 'DAS' });
    await screen.findByText('Replaced a failed disk');
    expect(screen.queryByLabelText('Filter by user')).not.toBeInTheDocument();
  });

  it('offers an administrator a user filter that reaches the API', async () => {
    const user = userEvent.setup();
    renderTable({ service: 'DAS', permissionMap: ADMIN_PERMISSIONS });
    await screen.findByText('Replaced a failed disk');

    const filter = await screen.findByLabelText('Filter by user');
    await user.selectOptions(filter, 'user-2');

    await waitFor(() => expect(lastTaskQuery().get('user_id')).toBe('user-2'));
  });

  it('does not offer the user filter on the global view', async () => {
    renderTable({ permissionMap: ADMIN_PERMISSIONS });
    await screen.findByText('Replaced a failed disk');
    expect(screen.queryByLabelText('Filter by user')).not.toBeInTheDocument();
  });

  it('shows an empty state that distinguishes filtered from unfiltered', async () => {
    mockTasks([]);
    const user = userEvent.setup();
    renderTable();

    expect(await screen.findByText('No tasks have been recorded yet.')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Search tasks'), 'nothing');
    expect(
      await screen.findByText('No tasks match the current filters.'),
    ).toBeInTheDocument();
  });

  it('surfaces a load failure with a retry', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
    vi.mocked(api.get).mockRejectedValue(
      new ApiError(500, { code: 'server_error', message: 'Unable to load tasks.' }),
    );
    renderTable();

    expect(await screen.findByText('Unable to load tasks.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
