import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { ApiError, request } from '@/lib/api';
import { AuthShell } from './AuthShell';
import { PasswordRules } from './PasswordRules';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  if (!token) {
    return (
      <AuthShell title="Invalid link">
        <Alert tone="error">
          This password reset link is missing its token. Please request a new link.
        </Alert>
        <p className="mt-5 text-center text-sm">
          <Link to="/forgot-password" className="font-medium text-brand-700 hover:underline">
            Request a new link
          </Link>
        </p>
      </AuthShell>
    );
  }

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
      await request('/auth/reset-password', {
        method: 'POST',
        body: {
          token,
          new_password: newPassword,
          confirm_password: confirmPassword,
        },
        skipRetry: true,
      });
      navigate('/login', {
        replace: true,
        state: { notice: 'Your password has been reset. You can now sign in.' },
      });
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError('Unable to reset your password. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

        <PasswordRules />

        <Field
          label="New password"
          type="password"
          name="new-password"
          autoComplete="new-password"
          required
          autoFocus
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
          Reset password
        </Button>

        <p className="text-center text-sm">
          <Link to="/login" className="font-medium text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
