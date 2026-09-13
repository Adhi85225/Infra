/**
 * Dashboard task analytics: figures come from the API, filters are shared, and
 * every drill-down lands on a page that already exists.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { PermissionMap } from '@/auth/permissions';
import type { AccessLevel, Permission, TaskAnalytics as Analytics } from '@/lib/types';
import { TaskAnalytics } from './TaskAnalytics';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const { api } = await import('@/lib/api');

/** The real routes these modules own, as the server reports them. */
const MODULE_ROUTES: Record<string, string> = {
  TASK_UPDATES: '/task-updates',
  ACCESS_MANAGEMENT: '/access-management',
  DAS_ONBOARDING: '/das-onboarding',
  ILO_INVENTORY: '/ilo-inventory',
  ZABBIX: '/zabbix',
  NEXUS: '/nexus',
  SERVERS: '/servers',
};

function permission(moduleKey: string, level: AccessLevel): Permission {
  return {
    module_key: moduleKey,
    module_name: moduleKey,
    icon: null,
    route: MODULE_ROUTES[moduleKey] ?? `/${moduleKey.toLowerCase()}`,
    description: null,
    sort_order: 10,
    is_implemented: true,
    access_level: level,
    can_view: level !== 'NONE',
    can_manage: level === 'COMPLETE',
  };
}

const USER_PERMISSIONS = [
  permission('TASK_UPDATES', 'COMPLETE'),
  permission('ACCESS_MANAGEMENT', 'READ_ONLY'),
  ...['DAS_ONBOARDING', 'ILO_INVENTORY', 'ZABBIX', 'NEXUS', 'SERVERS'].map((key) =>
    permission(key, 'READ_ONLY'),
  ),
];

const ADMIN_PERMISSIONS = USER_PERMISSIONS.map((entry) =>
  entry.module_key === 'ACCESS_MANAGEMENT' ? permission('ACCESS_MANAGEMENT', 'COMPLETE') : entry,
);

function toMap(permissions: Permission[]): PermissionMap {
  return Object.fromEntries(permissions.map((entry) => [entry.module_key, entry]));
}

const ANALYTICS: Analytics = {
  total: 128,
  by_status: [
    { status: 'Created', count: 18 },
    { status: 'Inprogress', count: 34 },
    { status: 'Onhold', count: 12 },
    { status: 'Completed', count: 54 },
    { status: 'Triage', count: 10 },
  ],
  by_service: [
    { service: 'Access Management', module_key: 'ACCESS_MANAGEMENT', count: 32 },
    { service: 'DAS', module_key: 'DAS_ONBOARDING', count: 21 },
    { service: 'ILO', module_key: 'ILO_INVENTORY', count: 15 },
    { service: 'Zabbix', module_key: 'ZABBIX', count: 24 },
    { service: 'Nexus', module_key: 'NEXUS', count: 10 },
    { service: 'Servers', module_key: 'SERVERS', count: 26 },
  ],
  trend: [
    { date: '2026-09-12', created: 4, completed: 2 },
    { date: '2026-09-13', created: 6, completed: 3 },
  ],
  trend_from: '2026-09-12',
  trend_to: '2026-09-13',
  recent: [
    {
      id: 'task-1',
      task_date: '2026-09-13',
      reference_number: 'INC-1024',
      site_name: 'Chennai DC',
      description: 'Replaced a failed disk',
      status: 'Inprogress',
      remarks: null,
      service: 'DAS',
      user_id: 'user-1',
      user_name: 'Normal User',
      user_email: 'user@test.internal',
      created_at: '2026-09-13T00:00:00Z',
      updated_at: '2026-09-13T00:00:00Z',
      can_edit: true,
    },
  ],
};

function mockApi(analytics: Analytics = ANALYTICS) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith('/users')) {
      return Promise.resolve({
        items: [{ id: 'user-2', full_name: 'Other User' }],
        total: 1,
        limit: 100,
        offset: 0,
      });
    }
    return Promise.resolve(analytics);
  });
}

function analyticsCalls() {
  return vi.mocked(api.get).mock.calls.filter(([path]) =>
    String(path).startsWith('/tasks/analytics'),
  );
}

function lastQuery(): URLSearchParams {
  const calls = analyticsCalls();
  return new URLSearchParams(String(calls[calls.length - 1]![0]).split('?')[1] ?? '');
}

/** Renders the section plus stand-ins for the pages it navigates to. */
function renderAnalytics(permissions: Permission[] = USER_PERMISSIONS) {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route
          path="/dashboard"
          element={<TaskAnalytics permissionMap={toMap(permissions)} permissions={permissions} />}
        />
        <Route path="/task-updates" element={<p>TASK UPDATES PAGE</p>} />
        <Route path="/das-onboarding" element={<p>DAS ONBOARDING PAGE</p>} />
        <Route path="/zabbix" element={<p>ZABBIX PAGE</p>} />
        <Route path="/servers" element={<p>SERVERS PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TaskAnalytics', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    mockApi();
  });

  it('renders KPI figures from the API', async () => {
    renderAnalytics();
    const summary = await screen.findByRole('group', { name: 'Task summary' });

    const expected: [string, string][] = [
      ['Total tasks', '128'],
      ['Created', '18'],
      ['Inprogress', '34'],
      ['Onhold', '12'],
      ['Completed', '54'],
      ['Triage', '10'],
    ];
    for (const [label, value] of expected) {
      // Every KPI card is a button: each one drills through to Task Updates.
      const card = within(summary).getByText(label).closest('button')!;
      expect(within(card).getByText(value)).toBeInTheDocument();
    }
  });

  it('answers the whole dashboard with a single aggregated request', async () => {
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });
    // One analytics call -- no per-widget fetching, and no task rows downloaded
    // just to be counted in the browser.
    expect(analyticsCalls()).toHaveLength(1);
    expect(vi.mocked(api.get).mock.calls.some(([p]) => String(p).startsWith('/tasks?'))).toBe(false);
  });

  it('shows every service in the bar chart with its count', async () => {
    renderAnalytics();
    const chart = within(await screen.findByRole('region', { name: 'Tasks by service' }));

    const expected: [string, string][] = [
      ['Access Management', '32'],
      ['DAS', '21'],
      ['ILO', '15'],
      ['Zabbix', '24'],
      ['Nexus', '10'],
      ['Servers', '26'],
    ];
    for (const [service, count] of expected) {
      expect(chart.getByText(service)).toBeInTheDocument();
      expect(chart.getByText(count)).toBeInTheDocument();
    }
  });

  it('shows every status in the donut legend with count and share', async () => {
    renderAnalytics();
    const donut = within(await screen.findByRole('region', { name: 'Tasks by status' }));

    expect(donut.getByText('Completed')).toBeInTheDocument();
    expect(donut.getByText('54')).toBeInTheDocument();
    // 54 of 128 -> 42%.
    expect(donut.getByText('42%')).toBeInTheDocument();
  });

  it('navigates to the EXISTING service page from the bar chart', async () => {
    const user = userEvent.setup();
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });

    // The DAS bar must open /das-onboarding -- the page that already exists --
    // not a service page invented by Task Updates.
    await user.click(screen.getByTitle(/^DAS: 21 tasks/));
    expect(await screen.findByText('DAS ONBOARDING PAGE')).toBeInTheDocument();
  });

  it('navigates to the existing service page from a quick-access card', async () => {
    const user = userEvent.setup();
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });

    const services = within(screen.getByRole('region', { name: 'Services' }));
    const card = services.getByRole('link', { name: /Zabbix/ });
    expect(card).toHaveAttribute('href', '/zabbix');
    await user.click(card);
    expect(await screen.findByText('ZABBIX PAGE')).toBeInTheDocument();
  });

  it('drills from a KPI card through to Task Updates with the status filter', async () => {
    const user = userEvent.setup();
    renderAnalytics();
    const summary = await screen.findByRole('group', { name: 'Task summary' });

    await user.click(within(summary).getByRole('button', { name: /Completed/ }));
    expect(await screen.findByText('TASK UPDATES PAGE')).toBeInTheDocument();
  });

  it('applies the date filter to the request', async () => {
    const user = userEvent.setup();
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });

    await user.click(screen.getByRole('button', { name: 'today' }));

    const now = new Date();
    const iso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    await waitFor(() => expect(lastQuery().get('date_from')).toBe(iso));
    expect(lastQuery().get('date_to')).toBe(iso);
  });

  it('applies the service and status filters to the request', async () => {
    const user = userEvent.setup();
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });

    await user.selectOptions(screen.getByLabelText('Filter by service'), 'DAS');
    await waitFor(() => expect(lastQuery().get('service')).toBe('DAS'));

    await user.selectOptions(screen.getByLabelText('Filter by status'), 'Onhold');
    await waitFor(() => expect(lastQuery().get('status')).toBe('Onhold'));
  });

  it('combines every filter into one request', async () => {
    const user = userEvent.setup();
    renderAnalytics(ADMIN_PERMISSIONS);
    await screen.findByRole('group', { name: 'Task summary' });

    await user.click(screen.getByRole('button', { name: 'today' }));
    await user.selectOptions(screen.getByLabelText('Filter by service'), 'DAS');
    await user.selectOptions(screen.getByLabelText('Filter by status'), 'Inprogress');
    await user.selectOptions(await screen.findByLabelText('Filter by user'), 'user-2');

    await waitFor(() => {
      const query = lastQuery();
      expect(query.get('service')).toBe('DAS');
      expect(query.get('status')).toBe('Inprogress');
      expect(query.get('user_id')).toBe('user-2');
      expect(query.get('date_from')).toBeTruthy();
    });
  });

  it('hides the user filter from a non-administrator', async () => {
    renderAnalytics();
    await screen.findByRole('group', { name: 'Task summary' });
    expect(screen.queryByLabelText('Filter by user')).not.toBeInTheDocument();
  });

  it('offers the user filter to an administrator', async () => {
    renderAnalytics(ADMIN_PERMISSIONS);
    await screen.findByRole('group', { name: 'Task summary' });
    expect(await screen.findByLabelText('Filter by user')).toBeInTheDocument();
  });

  it('lists recent tasks and links to the full table', async () => {
    renderAnalytics();
    const recent = within(await screen.findByRole('region', { name: 'Recent tasks' }));

    expect(recent.getByText('Replaced a failed disk')).toBeInTheDocument();
    expect(recent.getByText('INC-1024')).toBeInTheDocument();
    expect(recent.getByRole('link', { name: 'View all tasks →' })).toHaveAttribute(
      'href',
      '/task-updates',
    );
  });

  it('shows empty states rather than blank chart frames', async () => {
    mockApi({
      ...ANALYTICS,
      total: 0,
      by_status: ANALYTICS.by_status.map((row) => ({ ...row, count: 0 })),
      by_service: ANALYTICS.by_service.map((row) => ({ ...row, count: 0 })),
      trend: [{ date: '2026-09-13', created: 0, completed: 0 }],
      recent: [],
    });
    renderAnalytics();

    await waitFor(() =>
      expect(screen.getAllByText('No task data available yet.').length).toBeGreaterThan(0),
    );
    expect(screen.getByText('No task data available for the selected filters.')).toBeInTheDocument();
    expect(screen.getByText('No task activity recorded yet.')).toBeInTheDocument();
  });

  it('surfaces an API failure with a retry', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
    vi.mocked(api.get).mockRejectedValue(
      new ApiError(500, { code: 'server_error', message: 'Unable to load task analytics.' }),
    );
    renderAnalytics();

    expect(await screen.findByText('Unable to load task analytics.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
