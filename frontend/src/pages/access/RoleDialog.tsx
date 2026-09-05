import { useEffect, useState, type FormEvent } from 'react';

import { ACCESS_LABELS, ASSIGNABLE_ACCESS_LEVELS } from '@/auth/permissions';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { AccessLevel, ModuleSummary, RoleWithPermissions } from '@/lib/types';

/**
 * Create or edit a role, including its module permission matrix.
 *
 * One dialog serves both cases: `role` is null when creating. The matrix is
 * built from the module catalogue, so a module added to the backend registry
 * appears here with no change to this file.
 */
export function RoleDialog({
  open,
  role,
  modules,
  onClose,
  onSaved,
}: {
  open: boolean;
  role: RoleWithPermissions | null;
  modules: ModuleSummary[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const isEdit = role !== null;

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [matrix, setMatrix] = useState<Record<string, AccessLevel>>({});
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Seed the form when the dialog opens, or when a different role is selected.
  // Keyed on identity rather than the whole object so typing does not reset it.
  useEffect(() => {
    if (!open) return;
    setName(role?.name ?? '');
    setDescription(role?.description ?? '');
    setMatrix(
      role?.permissions ??
        Object.fromEntries(modules.map((module) => [module.key, 'NONE' as AccessLevel])),
    );
    setError(null);
    setFieldErrors({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, role?.id]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    setSubmitting(true);

    try {
      if (isEdit && role) {
        await api.patch<RoleWithPermissions>(`/roles/${role.id}`, { name, description });
        // Super Admin permissions are implicit and rejected by the API.
        if (!role.is_superuser) {
          await api.put<RoleWithPermissions>(`/roles/${role.id}/permissions`, {
            permissions: matrix,
          });
        }
        notify('Role updated.', 'success');
      } else {
        await api.post<RoleWithPermissions>('/roles', {
          name,
          description: description || null,
          permissions: matrix,
        });
        notify('Role created.', 'success');
      }
      onSaved();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError('Unable to save the role.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const matrixLocked = Boolean(role?.is_superuser);

  return (
    <Modal
      open={open}
      title={isEdit ? `Edit ${role?.name}` : 'Create role'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="role-form" loading={submitting}>
            {isEdit ? 'Save changes' : 'Create role'}
          </Button>
        </>
      }
    >
      <form id="role-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

        {role?.is_superuser && (
          <Alert tone="info">
            Super Admin access is implicit and covers every module, including modules added later.
            Its permissions cannot be edited.
          </Alert>
        )}

        <Field
          label="Role name"
          required
          value={name}
          error={fieldErrors.name}
          onChange={(event) => setName(event.target.value)}
          hint={
            isEdit
              ? `Machine key: ${role?.key} (immutable)`
              : 'A machine key is derived automatically, e.g. "Asset Manager" → ASSET_MANAGER.'
          }
        />

        <div>
          <label htmlFor="role-description" className="field-label">
            Description
          </label>
          <textarea
            id="role-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="field-input"
            placeholder="What is this role for?"
          />
        </div>

        <fieldset disabled={matrixLocked}>
          <legend className="field-label">Module permissions</legend>
          <div className="max-h-64 overflow-y-auto rounded-md border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <caption className="sr-only">Access level this role grants on each module</caption>
              <tbody className="divide-y divide-slate-100">
                {modules.map((module) => (
                  <tr key={module.key}>
                    <td className="px-3 py-2">
                      <span aria-hidden="true" className="mr-2">
                        {module.icon}
                      </span>
                      <span className="text-slate-800">{module.name}</span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <select
                        value={matrixLocked ? 'COMPLETE' : (matrix[module.key] ?? 'NONE')}
                        aria-label={`Access level for ${module.name}`}
                        onChange={(event) =>
                          setMatrix((current) => ({
                            ...current,
                            [module.key]: event.target.value as AccessLevel,
                          }))
                        }
                        className="field-input max-w-[11rem] py-1"
                      >
                        {ASSIGNABLE_ACCESS_LEVELS.map((level) => (
                          <option key={level} value={level}>
                            {ACCESS_LABELS[level]}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {fieldErrors.modules && (
            <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
              {fieldErrors.modules}
            </p>
          )}
          <p className="mt-1.5 text-xs text-slate-500">
            A user holding several roles receives the highest level any of them grants.
          </p>
        </fieldset>
      </form>
    </Modal>
  );
}
