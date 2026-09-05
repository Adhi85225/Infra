import { useEffect, useState, type FormEvent } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import type { Role, User, UserStatus } from '@/lib/types';

export function EditUserDialog({
  user,
  roles,
  onClose,
  onSaved,
}: {
  user: User | null;
  roles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [status, setStatus] = useState<UserStatus>('ACTIVE');
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) return;
    setFirstName(user.first_name);
    setLastName(user.last_name);
    setJobTitle(user.job_title ?? '');
    setStatus(user.status);
    setSelectedRoles(user.roles.map((role) => role.key));
    setError(null);
    setFieldErrors({});
  }, [user]);

  if (!user) return null;

  const toggleRole = (key: string) => {
    setSelectedRoles((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    setSubmitting(true);

    const originalRoles = [...user.roles.map((role) => role.key)].sort();
    const nextRoles = [...selectedRoles].sort();
    const rolesChanged = JSON.stringify(originalRoles) !== JSON.stringify(nextRoles);

    try {
      await api.patch<User>(`/users/${user.id}`, {
        first_name: firstName,
        last_name: lastName,
        job_title: jobTitle || null,
        // Only send a status change when it actually changed: the API rejects
        // an admin changing their own status.
        ...(status !== user.status ? { status } : {}),
      });

      if (rolesChanged) {
        await api.put<User>(`/users/${user.id}/roles`, { role_keys: selectedRoles });
      }

      notify('User updated.', 'success');
      onSaved();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError('Unable to save changes.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      title={`Edit ${user.full_name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="edit-user-form" loading={submitting}>
            Save changes
          </Button>
        </>
      }
    >
      <form id="edit-user-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">{user.email}</div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="First name"
            required
            value={firstName}
            error={fieldErrors.first_name}
            onChange={(event) => setFirstName(event.target.value)}
          />
          <Field
            label="Last name"
            required
            value={lastName}
            error={fieldErrors.last_name}
            onChange={(event) => setLastName(event.target.value)}
          />
        </div>

        <Field
          label="Job title"
          value={jobTitle}
          onChange={(event) => setJobTitle(event.target.value)}
        />

        <div>
          <label htmlFor="edit-status" className="field-label">
            Account status
          </label>
          <select
            id="edit-status"
            value={status}
            onChange={(event) => setStatus(event.target.value as UserStatus)}
            className="field-input"
          >
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
            <option value="SUSPENDED">Suspended</option>
          </select>
          <p className="mt-1.5 text-xs text-slate-500">
            Anything other than Active blocks sign-in and ends existing sessions.
          </p>
        </div>

        <fieldset>
          <legend className="field-label">Roles</legend>
          <div className="flex flex-col gap-2 rounded-md border border-slate-200 p-3">
            {roles.map((role) => (
              <label key={role.id} className="flex items-center gap-2.5 text-sm">
                <input
                  type="checkbox"
                  checked={selectedRoles.includes(role.key)}
                  onChange={() => toggleRole(role.key)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="font-medium text-slate-800">{role.name}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
