import { useEffect, useState } from 'react';

import { request } from '@/lib/api';
import type { PasswordPolicy } from '@/lib/types';

/**
 * Renders the password policy fetched from the API.
 *
 * The rules are never hard-coded here: the server is the single source of
 * truth, so changing the policy in configuration updates this list too.
 */
export function PasswordRules() {
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);

  useEffect(() => {
    let cancelled = false;
    void request<PasswordPolicy>('/auth/password-policy', { skipRetry: true })
      .then((result) => {
        if (!cancelled) setPolicy(result);
      })
      .catch(() => {
        /* the server still enforces the policy; the hint is optional */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!policy) return null;

  const rules = [
    `At least ${policy.min_length} characters`,
    policy.require_uppercase ? 'An uppercase letter' : null,
    policy.require_lowercase ? 'A lowercase letter' : null,
    policy.require_digit ? 'A number' : null,
    policy.require_symbol ? 'A special character' : null,
    policy.history_depth > 0 ? `Not one of your last ${policy.history_depth} passwords` : null,
  ].filter((rule): rule is string => rule !== null);

  return (
    <div className="rounded-md bg-slate-50 px-4 py-3">
      <p className="text-xs font-semibold text-slate-700">Your password must contain:</p>
      <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs text-slate-600">
        {rules.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
    </div>
  );
}
