import { useState, type FormEvent } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { ApiError, api } from '@/lib/api';
import type { Role, User } from '@/lib/types';

interface CreateUserResponse {
  user: User;
  temporary_password: string;
  email_delivered: boolean;
}

export function CreateUserDialog({
  open,
  roles,
  onClose,
  onCreated,
}: {
  open: boolean;
  roles: Role[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<CreateUserResponse | null>(null);

  const reset = () => {
    setEmail('');
    setFirstName('');
    setLastName('');
    setJobTitle('');
    setSelectedRoles([]);
    setError(null);
    setFieldErrors({});
    setCreated(null);
  };

  const close = () => {
    reset();
    onClose();
  };

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
    try {
      const result = await api.post<CreateUserResponse>('/users', {
        email,
        first_name: firstName,
        last_name: lastName,
        job_title: jobTitle || null,
        role_keys: selectedRoles,
      });
      setCreated(result);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError('Unable to create the user.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // After creation the temporary password is shown once: with SMTP not yet
  // wired up, this is how an admin hands the credential over.
  if (created) {
    const finish = () => {
      reset();
      onCreated();
    };
    return (
      <Modal
        open={open}
        title="User created"
        onClose={finish}
        footer={<Button onClick={finish}>Done</Button>}
      >
        <div className="flex flex-col gap-4">
          <Alert tone="success">
            <span className="font-medium">{created.user.full_name}</span> was created and must
            change this password at first sign-in.
          </Alert>

          <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Temporary password
            </p>
            <p className="mt-1 select-all break-all font-mono text-sm text-slate-900">
              {created.temporary_password}
            </p>
          </div>

          <Alert tone="warning">
            This password is shown only once. Email delivery is not configured yet, so pass it to
            the user through a secure channel.
          </Alert>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      title="Create user"
      onClose={close}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" form="create-user-form" loading={submitting}>
            Create user
          </Button>
        </>
      }
    >
      <form id="create-user-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

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
          label="Email address"
          type="email"
          required
          value={email}
          error={fieldErrors.email}
          onChange={(event) => setEmail(event.target.value)}
          hint="Used as the sign-in identifier."
        />

        <Field
          label="Job title"
          value={jobTitle}
          onChange={(event) => setJobTitle(event.target.value)}
        />

        <fieldset>
          <legend className="field-label">Roles</legend>
          <div className="flex flex-col gap-2 rounded-md border border-slate-200 p-3">
            {roles.map((role) => (
              <label key={role.id} className="flex items-start gap-2.5 text-sm">
                <input
                  type="checkbox"
                  checked={selectedRoles.includes(role.key)}
                  onChange={() => toggleRole(role.key)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600
                             focus:ring-brand-500"
                />
                <span>
                  <span className="font-medium text-slate-800">{role.name}</span>
                  {role.description && (
                    <span className="block text-xs text-slate-500">{role.description}</span>
                  )}
                </span>
              </label>
            ))}
          </div>
          {fieldErrors.roles && (
            <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
              {fieldErrors.roles}
            </p>
          )}
          <p className="mt-1.5 text-xs text-slate-500">
            A user may hold several roles; their access is the highest level each role grants.
          </p>
        </fieldset>
      </form>
    </Modal>
  );
}
