/**
 * The dashboard is the task overview.
 *
 * The module-card grid it used to open with was removed: it repeated the
 * sidebar, and repeated the service quick-access cards in the analytics.
 * Navigation lives in the sidebar now, so these tests assert the grid is gone
 * and that the analytics take its place.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { Permission, User } from '@/lib/types';

const mockAuth = vi.fn();
vi.mock('@/auth/AuthContext', () => ({ useAuth: () => mockAuth() }));

// The analytics fetch on mount; this suite is about what the dashboard
// chooses to render, not about the charts themselves.
vi.mock('./dashboard/TaskAnalytics', () => ({
  TaskAnalytics: () => <p>TASK ANALYTICS</p>,
}));

const { DashboardPage } = await import('./DashboardPage');

function permission(key: string, name: string, level: Permission['access_level']): Permission {
  return {
    module_key: key,
    module_name: name,
    icon: null,
    route: `/${key.toLowerCase().replace(/_/g, '-')}`,
    description: `${name} description`,
    sort_order: 10,
    is_implemented: false,
    access_level: level,
    can_view: level !== 'NONE',
    can_manage: level === 'COMPLETE',
  };
}

const USER = { first_name: 'Ada', roles: [{ name: 'Asset Manager' }] } as unknown as User;

function renderDashboard(permissions: Permission[]) {
  mockAuth.mockReturnValue({ user: USER, permissions });
  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe('DashboardPage', () => {
  it('no longer renders a grid of module cards', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('TASK_UPDATES', 'Task Updates', 'COMPLETE'),
      permission('ASSET_INVENTORY', 'Asset Inventory', 'COMPLETE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
    ]);

    // The sidebar navigates; the dashboard reports.
    expect(screen.queryByRole('link', { name: /Asset Inventory/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Zabbix/ })).not.toBeInTheDocument();
  });

  it('shows the task analytics to a user who can open Task Updates', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('TASK_UPDATES', 'Task Updates', 'COMPLETE'),
    ]);
    expect(screen.getByText('TASK ANALYTICS')).toBeInTheDocument();
  });

  it('hides the analytics from a user who cannot open Task Updates', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('TASK_UPDATES', 'Task Updates', 'NONE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
    ]);

    expect(screen.queryByText('TASK ANALYTICS')).not.toBeInTheDocument();
    expect(screen.getByText('Nothing to show here')).toBeInTheDocument();
  });

  it('counts only the tools that are shown', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
      permission('NEXUS', 'Nexus', 'NONE'),
    ]);
    expect(screen.getByText(/You have access to 1 tool\./)).toBeInTheDocument();
  });

  it('shows an empty state when no tools are available', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'NONE'),
      permission('NEXUS', 'Nexus', 'NONE'),
    ]);
    expect(screen.getByText('No tools available')).toBeInTheDocument();
  });
});
