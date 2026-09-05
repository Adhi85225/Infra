import { useCallback, useEffect, useState } from 'react';

import { can, type PermissionMap } from '@/auth/permissions';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/Badge';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { Page, Role, User, UserStatus } from '@/lib/types';
import { CreateUserDialog } from './CreateUserDialog';
import { EditUserDialog } from './EditUserDialog';

const PAGE_SIZE = 20;

export function UsersTab({ permissionMap }: { permissionMap: PermissionMap }) {
  const { notify } = useToast();
  const canManage = can(permissionMap, 'ACCESS_MANAGEMENT', 'UPDATE');
  const canCreate = can(permissionMap, 'ACCESS_MANAGEMENT', 'CREATE');

  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<UserStatus | ''>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (search.trim()) params.set('search', search.trim());
      if (statusFilter) params.set('status', statusFilter);

      const page = await api.get<Page<User>>(`/users?${params.toString()}`);
      setUsers(page.items);
      setTotal(page.total);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load users.');
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter]);

  // Debounced so typing in the search box does not spam the API.
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  // Roles are fetched once. Reloading them alongside the user list gave the
  // `roles` array a new identity on every search keystroke, re-rendering the
  // open dialog for no reason.
  useEffect(() => {
    let cancelled = false;
    void api
      .get<Role[]>('/roles')
      .then((roleList) => {
        if (!cancelled) setRoles(roleList);
      })
      .catch(() => {
        /* the dialogs degrade to an empty role list; the list view still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const resetPassword = useCallback(
    async (user: User) => {
      try {
        const result = await api.post<{ temporary_password: string; email_delivered: boolean }>(
          `/users/${user.id}/reset-password`,
        );
        notify(`Temporary password for ${user.email}: ${result.temporary_password}`, 'success');
        void load();
      } catch (caught) {
        notify(caught instanceof ApiError ? caught.message : 'Unable to reset password.', 'error');
      }
    },
    [notify, load],
  );

  // Stable identities: the dialogs below are long-lived while open, and new
  // callback props on every parent render would re-render them needlessly.
  const closeCreate = useCallback(() => setCreating(false), []);
  const closeEdit = useCallback(() => setEditing(null), []);
  const afterCreate = useCallback(() => {
    setCreating(false);
    void load();
  }, [load]);
  const afterEdit = useCallback(() => {
    setEditing(null);
    void load();
  }, [load]);

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
          placeholder="Search name or email…"
          aria-label="Search users"
          className="field-input max-w-xs"
        />
        <select
          value={statusFilter}
          onChange={(event) => {
            setOffset(0);
            setStatusFilter(event.target.value as UserStatus | '');
          }}
          aria-label="Filter by status"
          className="field-input max-w-[10rem]"
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
          <option value="SUSPENDED">Suspended</option>
        </select>

        <div className="ml-auto">
          {canCreate && <Button onClick={() => setCreating(true)}>Create user</Button>}
        </div>
      </div>

      {!canManage && (
        <div className="mb-4">
          <Alert tone="info">
            You have read-only access to Access Management. Editing is disabled.
          </Alert>
        </div>
      )}

      {loading && users.length === 0 ? (
        <LoadingState label="Loading users…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : users.length === 0 ? (
        <EmptyState
          title="No users found"
          description={
            search || statusFilter
              ? 'No users match the current filters.'
              : 'No users have been created yet.'
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Users and their assigned roles</caption>
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">Name</th>
                <th scope="col" className="px-4 py-3 font-semibold">Email</th>
                <th scope="col" className="px-4 py-3 font-semibold">Roles</th>
                <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                <th scope="col" className="px-4 py-3 font-semibold">Last sign-in</th>
                {canManage && <th scope="col" className="px-4 py-3 text-right font-semibold">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="font-medium text-slate-900">{user.full_name}</span>
                    {user.must_change_password && (
                      <span className="ml-2 text-xs text-amber-600">password change pending</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{user.email}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {user.roles.length === 0 ? (
                      <span className="text-slate-400">None</span>
                    ) : (
                      user.roles.map((role) => role.name).join(', ')
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={user.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {user.last_login_at
                      ? new Date(user.last_login_at).toLocaleString()
                      : 'Never'}
                  </td>
                  {canManage && (
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(user)}>
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void resetPassword(user)}
                      >
                        Reset password
                      </Button>
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

      <CreateUserDialog
        open={creating}
        roles={roles}
        onClose={closeCreate}
        onCreated={afterCreate}
      />

      <EditUserDialog
        user={editing}
        roles={roles}
        onClose={closeEdit}
        onSaved={afterEdit}
      />
    </div>
  );
}
