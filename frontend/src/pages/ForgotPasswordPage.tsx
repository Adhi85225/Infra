import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { ApiError, request } from '@/lib/api';
import { AuthShell } from './AuthShell';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await request('/auth/forgot-password', {
        method: 'POST',
        body: { email },
        skipRetry: true,
      });
      setSubmitted(true);
    } catch (caught) {
      // A rate limit is the only error worth surfacing here; anything else
      // would risk hinting at whether the address exists.
      setError(
        caught instanceof ApiError && caught.status === 429
          ? caught.message
          : 'Unable to submit the request. Please try again shortly.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <AuthShell title="Check your email">
        <Alert tone="success">
          If an account exists for that email address, a password reset link has been sent. The
          link expires shortly and can only be used once.
        </Alert>
        <p className="mt-5 text-center text-sm">
          <Link to="/login" className="font-medium text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Forgot password"
      subtitle="Enter your email address and we'll send you a reset link."
    >
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
        />

        <Button type="submit" loading={submitting} className="w-full">
          Send reset link
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
