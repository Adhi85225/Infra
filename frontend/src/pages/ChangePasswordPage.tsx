import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { AuthShell } from './AuthShell';
import { PasswordRules } from './PasswordRules';

/**
 * Serves two situations:
 *  - the mandatory first-login change (rendered standalone, no navigation), and
 *  - a voluntary change from inside the app.
 */
export function ChangePasswordPage() {
  const { changePassword, mustChangePassword, logout } = useAuth();
  const navigate = useNavigate();
  const { notify } = useToast();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});

    if (newPassword !== confirmPassword) {
      setFieldErrors({ confirm_password: 'Passwords do not match.' });
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword, confirmPassword);
      notify('Your password has been changed.', 'success');
      navigate('/dashboard', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError('Unable to change your password. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const form = (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {error && <Alert tone="error">{error}</Alert>}

      <PasswordRules />

      <Field
        label="Current password"
        type="password"
        name="current-password"
        autoComplete="current-password"
        required
        autoFocus
        value={currentPassword}
        error={fieldErrors.current_password}
        onChange={(event) => setCurrentPassword(event.target.value)}
      />

      <Field
        label="New password"
        type="password"
        name="new-password"
        autoComplete="new-password"
        required
        value={newPassword}
        error={fieldErrors.password ?? fieldErrors.new_password}
        onChange={(event) => setNewPassword(event.target.value)}
      />

      <Field
        label="Confirm new password"
        type="password"
        name="confirm-password"
        autoComplete="new-password"
        required
        value={confirmPassword}
        error={fieldErrors.confirm_password}
        onChange={(event) => setConfirmPassword(event.target.value)}
      />

      <Button type="submit" loading={submitting} className="w-full">
        Change password
      </Button>
    </form>
  );

  // First login: the user has nowhere else to go until this is done.
  if (mustChangePassword) {
    return (
      <AuthShell
        title="Set your password"
        subtitle="Before you continue, please replace the password you were given."
      >
        {form}
        <div className="mt-5 border-t border-slate-200 pt-4 text-center">
          <button
            type="button"
            onClick={() => void logout()}
            className="text-sm text-slate-500 hover:text-slate-700 hover:underline"
          >
            Sign out instead
          </button>
        </div>
      </AuthShell>
    );
  }

  return (
    <div className="max-w-lg">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Change password</h2>
        <p className="mt-1 text-sm text-slate-500">
          Changing your password signs out every other device.
        </p>
      </header>
      <div className="rounded-lg border border-slate-200 bg-white p-6">{form}</div>
    </div>
  );
}
