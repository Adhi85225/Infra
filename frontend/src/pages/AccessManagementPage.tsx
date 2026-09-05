import { useState } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { AuditTab } from './access/AuditTab';
import { RolesTab } from './access/RolesTab';
import { UsersTab } from './access/UsersTab';

type Tab = 'users' | 'roles' | 'audit';

const TABS: { id: Tab; label: string }[] = [
  { id: 'users', label: 'Users' },
  { id: 'roles', label: 'Roles & permissions' },
  { id: 'audit', label: 'Audit log' },
];

export function AccessManagementPage() {
  const { permissionMap } = useAuth();
  const [tab, setTab] = useState<Tab>('users');

  return (
    <div>
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Access Management</h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage users, roles, module permissions and account status.
        </p>
      </header>

      <div className="mb-5 border-b border-slate-200">
        <div role="tablist" aria-label="Access management sections" className="-mb-px flex gap-1">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              role="tab"
              type="button"
              aria-selected={tab === entry.id}
              onClick={() => setTab(entry.id)}
              className={`border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                tab === entry.id
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'users' && <UsersTab permissionMap={permissionMap} />}
      {tab === 'roles' && <RolesTab permissionMap={permissionMap} />}
      {tab === 'audit' && <AuditTab />}
    </div>
  );
}
