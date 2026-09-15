/**
 * Existing service pages show their own tasks.
 *
 * The point under test is the integration: `/das-onboarding` — the route and
 * module that already existed — renders T1 filtered to `service=DAS`, with the
 * Action column. No route was invented for it, and nothing moved under
 * `/task-updates`.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '@/components/ui/Toast';
import type { AccessLevel, Permission, Task } from '@/lib/types';
import { SERVICE_MODULES, TASK_SERVICES, serviceForModule } from '@/lib/types';

const mockAuth = vi.fn();
vi.mock('@/auth/AuthContext', () => ({ useAuth: () => mockAuth() }));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const { api } = await import('@/lib/api');
const { ServiceModulePage } = await import('./ServiceModulePage');

/** The routes these modules already own. */
const ROUTES: Record<string, string> = {
  ACCESS_MANAGEMENT: '/access-management',
  DAS_ONBOARDING: '/das-onboarding',
  ILO_INVENTORY: '/ilo-inventory',
  ZABBIX: '/zabbix',
  NEXUS: '/nexus',
  SERVERS: '/servers',
};

const NAMES: Record<string, string> = {
  ACCESS_MANAGEMENT: 'Access Management',
  DAS_ONBOARDING: 'DAS',
  ILO_INVENTORY: 'ILO',
  ZABBIX: 'Zabbix',
  NEXUS: 'Nexus',
  SERVERS: 'Patch Management',
};

function permission(moduleKey: string, level: AccessLevel): Permission {
  return {
    module_key: moduleKey,
    module_name: NAMES[moduleKey] ?? moduleKey,
    icon: null,
    route: ROUTES[moduleKey] ?? `/${moduleKey.toLowerCase()}`,
    description: `${NAMES[moduleKey]} description`,
    sort_order: 10,
    is_implemented: true,
    access_level: level,
    can_view: level !== 'NONE',
    can_manage: level === 'COMPLETE',
  };
}

function task(overrides: Partial<Task> = {}): Task {
  return {
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
    ...overrides,
  };
}

function mockTasks(items: Task[] = [task()]) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith('/users')) {
      return Promise.resolve({ items: [], total: 0, limit: 100, offset: 0 });
    }
    return Promise.resolve({ items, total: items.length, limit: 20, offset: 0 });
  });
}

function lastTaskQuery(): URLSearchParams {
  const calls = vi.mocked(api.get).mock.calls.filter(([p]) => String(p).startsWith('/tasks'));
  return new URLSearchParams(String(calls[calls.length - 1]![0]).split('?')[1] ?? '');
}

function renderAt(route: string, accessManagement: AccessLevel = 'READ_ONLY') {
  const permissions = Object.keys(ROUTES).map((key) =>
    permission(key, key === 'ACCESS_MANAGEMENT' ? accessManagement : 'COMPLETE'),
  );
  mockAuth.mockReturnValue({
    permissions,
    permissionMap: Object.fromEntries(permissions.map((p) => [p.module_key, p])),
  });

  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path="*" element={<ServiceModulePage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe('ServiceModulePage', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    mockTasks();
  });

  it('maps every service onto a module that is not under /task-updates', () => {
    for (const service of TASK_SERVICES) {
      const moduleKey = SERVICE_MODULES[service];
      expect(ROUTES[moduleKey]).toBeDefined();
      expect(ROUTES[moduleKey]!.startsWith('/task-updates')).toBe(false);
      expect(serviceForModule(moduleKey)).toBe(service);
    }
  });

  it('shows DAS tasks on the existing DAS page (route unchanged)', async () => {
    renderAt('/das-onboarding');

    // The page keeps its own existing name.
    expect(await screen.findByRole('heading', { name: /^DAS$/ })).toBeInTheDocument();
    await waitFor(() => expect(lastTaskQuery().get('service')).toBe('DAS'));
    expect(screen.getByText('Replaced a failed disk')).toBeInTheDocument();
  });

  it.each([
    ['/ilo-inventory', 'ILO', 'ILO'],
    ['/zabbix', 'Zabbix', 'Zabbix'],
    ['/nexus', 'Nexus', 'Nexus'],
    ['/servers', 'Patch Management', 'Patch Management'],
  ])('shows %s tasks filtered to %s', async (route, service, heading) => {
    renderAt(route);

    expect(await screen.findByRole('heading', { name: new RegExp(heading) })).toBeInTheDocument();
    await waitFor(() => expect(lastTaskQuery().get('service')).toBe(service));
  });

  it('renders the Action column with an edit control', async () => {
    renderAt('/das-onboarding');
    await screen.findByText('Replaced a failed disk');

    expect(screen.getByRole('columnheader', { name: 'Action' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Edit task: Replaced a failed disk' }),
    ).toBeInTheDocument();
  });

  it('tells a normal user the page is scoped to them', async () => {
    renderAt('/das-onboarding', 'READ_ONLY');
    expect(await screen.findByText(/These are your own DAS tasks/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Filter by user')).not.toBeInTheDocument();
  });

  it('gives an administrator the user filter and no scoping notice', async () => {
    renderAt('/das-onboarding', 'COMPLETE');
    await screen.findByText('Replaced a failed disk');

    expect(screen.queryByText(/These are your own DAS tasks/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Filter by user')).toBeInTheDocument();
  });

  it('is not found for a module that is not a service', async () => {
    renderAt('/reports');
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
