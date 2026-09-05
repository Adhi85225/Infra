/** The dashboard renders only the tools the signed-in user may open. */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { Permission, User } from '@/lib/types';

const mockAuth = vi.fn();
vi.mock('@/auth/AuthContext', () => ({ useAuth: () => mockAuth() }));

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
  it('shows only authorised modules', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('ASSET_INVENTORY', 'Asset Inventory', 'COMPLETE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
      permission('REPORTS', 'Reports', 'READ_ONLY'),
      permission('NEXUS', 'Nexus', 'NONE'),
      permission('CLOUD_INFORMATION', 'Cloud Information', 'NONE'),
    ]);

    expect(screen.getByText('Asset Inventory')).toBeInTheDocument();
    expect(screen.getByText('Zabbix')).toBeInTheDocument();
    expect(screen.getByText('Reports')).toBeInTheDocument();

    // Modules with no access are absent entirely -- not merely disabled.
    expect(screen.queryByText('Nexus')).not.toBeInTheDocument();
    expect(screen.queryByText('Cloud Information')).not.toBeInTheDocument();
  });

  it('does not render a card for the dashboard itself', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
    ]);
    expect(screen.queryByRole('link', { name: /Dashboard/ })).not.toBeInTheDocument();
  });

  it('counts only the tools that are shown', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('ZABBIX', 'Zabbix', 'READ_ONLY'),
      permission('NEXUS', 'Nexus', 'NONE'),
    ]);
    expect(screen.getByText(/You have access to 1 tool\./)).toBeInTheDocument();
  });

  it('links each card to the module route', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'COMPLETE'),
      permission('ASSET_INVENTORY', 'Asset Inventory', 'COMPLETE'),
    ]);
    expect(screen.getByRole('link', { name: /Asset Inventory/ })).toHaveAttribute(
      'href',
      '/asset-inventory',
    );
  });

  it('shows an empty state when no tools are available', () => {
    renderDashboard([
      permission('DASHBOARD', 'Dashboard', 'NONE'),
      permission('NEXUS', 'Nexus', 'NONE'),
    ]);
    expect(screen.getByText('No tools available')).toBeInTheDocument();
  });
});
