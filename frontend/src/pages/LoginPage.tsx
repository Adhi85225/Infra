import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { ApiError } from '@/lib/api';
import { AuthShell } from './AuthShell';

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
    return <Navigate to={from} replace />;
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Unable to sign in. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Sign in" subtitle="Use your work email address to continue.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

        <Field
          label="Email address"
          type="email"
          name="email"
          autoComplete="username"
          required
          autoFocus
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.internal"
        />

        <Field
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <Button type="submit" loading={submitting} className="w-full">
          Sign in
        </Button>

        <p className="text-center text-sm">
          <Link
            to="/forgot-password"
            className="font-medium text-brand-700 hover:text-brand-800 hover:underline"
          >
            Forgot your password?
          </Link>
        </p>
      </form>

      <p className="mt-6 border-t border-slate-200 pt-4 text-center text-xs text-slate-500">
        Accounts are created by an administrator. There is no public sign-up.
      </p>
    </AuthShell>
  );
}
