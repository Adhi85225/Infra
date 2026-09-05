import { useCallback, useEffect, useState } from 'react';

import { can, type PermissionMap } from '@/auth/permissions';
import { Alert } from '@/components/ui/Alert';
import { AccessBadge, Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { AccessLevel, ModuleSummary, Role, RoleWithPermissions } from '@/lib/types';
import { RoleDialog } from './RoleDialog';

/**
 * Role management: view, create, edit and delete roles, and configure each
 * role's module permissions.
 *
 * Roles are data, not code -- an administrator can add `AssetManager`,
 * `ReportViewer` and so on without a deployment. Seeded roles are protected.
 */
export function RolesTab({ permissionMap }: { permissionMap: PermissionMap }) {
  const { notify } = useToast();
  const canCreate = can(permissionMap, 'ACCESS_MANAGEMENT', 'CREATE');
  const canEdit = can(permissionMap, 'ACCESS_MANAGEMENT', 'UPDATE');

  const [roles, setRoles] = useState<Role[]>([]);
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [selected, setSelected] = useState<RoleWithPermissions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<RoleWithPermissions | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Role | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [roleList, moduleList] = await Promise.all([
        api.get<Role[]>('/roles'),
        api.get<ModuleSummary[]>('/modules'),
      ]);
      setRoles(roleList);
      setModules(moduleList);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load roles.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openDetails = useCallback(async (role: Role) => {
    try {
      setSelected(await api.get<RoleWithPermissions>(`/roles/${role.id}`));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load the role.');
    }
  }, []);

  const openEdit = useCallback(async (role: Role) => {
    try {
      setEditing(await api.get<RoleWithPermissions>(`/roles/${role.id}`));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load the role.');
    }
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/roles/${deleting.id}`);
      notify(`Role "${deleting.name}" deleted.`, 'success');
      setDeleting(null);
      void load();
    } catch (caught) {
      notify(caught instanceof ApiError ? caught.message : 'Unable to delete the role.', 'error');
    } finally {
      setDeleteBusy(false);
    }
  }, [deleting, notify, load]);

  // Stable identities so the dialogs are not re-rendered by unrelated updates.
  const closeCreate = useCallback(() => setCreating(false), []);
  const closeEdit = useCallback(() => setEditing(null), []);
  const closeDetails = useCallback(() => setSelected(null), []);
  const closeDelete = useCallback(() => setDeleting(null), []);
  const afterSave = useCallback(() => {
    setCreating(false);
    setEditing(null);
    void load();
  }, [load]);

  if (loading && roles.length === 0) return <LoadingState label="Loading roles…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <p className="text-sm text-slate-500">
          Roles determine what each user can reach. A user may hold several.
        </p>
        <div className="ml-auto">
          {canCreate && <Button onClick={() => setCreating(true)}>Create role</Button>}
        </div>
      </div>

      {!canEdit && (
        <div className="mb-4">
          <Alert tone="info">You have read-only access to roles.</Alert>
        </div>
      )}

      {roles.length === 0 ? (
        <EmptyState title="No roles" description="No roles have been configured." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Roles defined in this application</caption>
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">Role</th>
                <th scope="col" className="px-4 py-3 font-semibold">Key</th>
                <th scope="col" className="px-4 py-3 font-semibold">Users</th>
                <th scope="col" className="px-4 py-3 font-semibold">Type</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {roles.map((role) => (
                <tr key={role.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <span className="font-medium text-slate-900">{role.name}</span>
                    {role.description && (
                      <span className="block max-w-md truncate text-xs text-slate-500">
                        {role.description}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{role.key}</td>
                  <td className="px-4 py-3 text-slate-600">{role.user_count}</td>
                  <td className="px-4 py-3">
                    {role.is_superuser ? (
                      <Badge tone="slate">superuser</Badge>
                    ) : role.is_system ? (
                      <Badge tone="blue">system</Badge>
                    ) : (
                      <Badge tone="neutral">custom</Badge>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <Button variant="ghost" size="sm" onClick={() => void openDetails(role)}>
                      View
                    </Button>
                    {canEdit && (
                      <Button variant="ghost" size="sm" onClick={() => void openEdit(role)}>
                        Edit
                      </Button>
                    )}
                    {canEdit && role.is_deletable && (
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(role)}>
                        Delete
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Read-only detail view */}
      <Modal
        open={selected !== null}
        title={selected ? `${selected.name} permissions` : ''}
        onClose={closeDetails}
        footer={
          <Button variant="secondary" onClick={closeDetails}>
            Close
          </Button>
        }
      >
        {selected && (
          <div className="flex flex-col gap-3">
            {selected.description && (
              <p className="text-sm text-slate-600">{selected.description}</p>
            )}
            {selected.is_superuser && (
              <Alert tone="info">
                Super Admin access is implicit and automatically covers modules added in future.
              </Alert>
            )}
            <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200">
              <table className="min-w-full divide-y divide-slate-100 text-sm">
                <caption className="sr-only">Module permissions for {selected.name}</caption>
                <tbody className="divide-y divide-slate-100">
                  {Object.entries(selected.permissions).map(([moduleKey, level]) => (
                    <tr key={moduleKey}>
                      <td className="px-3 py-2 text-slate-700">
                        {modules.find((m) => m.key === moduleKey)?.name ?? moduleKey}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <AccessBadge level={level as AccessLevel} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete confirmation */}
      <Modal
        open={deleting !== null}
        title="Delete role"
        onClose={closeDelete}
        footer={
          <>
            <Button variant="secondary" onClick={closeDelete}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleteBusy} onClick={() => void confirmDelete()}>
              Delete role
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          Delete <span className="font-medium text-slate-900">{deleting?.name}</span>? This cannot
          be undone.
        </p>
        {(deleting?.user_count ?? 0) > 0 && (
          <div className="mt-3">
            <Alert tone="warning">
              This role is assigned to {deleting?.user_count} user(s). Reassign them first — the
              server will refuse the deletion otherwise.
            </Alert>
          </div>
        )}
      </Modal>

      <RoleDialog
        open={creating}
        role={null}
        modules={modules}
        onClose={closeCreate}
        onSaved={afterSave}
      />
      <RoleDialog
        open={editing !== null}
        role={editing}
        modules={modules}
        onClose={closeEdit}
        onSaved={afterSave}
      />
    </div>
  );
}
