import { useAuth } from '@/auth/AuthContext';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';

/**
 * Administrator settings.
 *
 * Phase 1 exposes read-only environment facts. Editable configuration arrives
 * with the Settings module proper in a later phase.
 */
export function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="max-w-3xl">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Settings</h2>
        <p className="mt-1 text-sm text-slate-500">Application configuration. Administrators only.</p>
      </header>

      <div className="flex flex-col gap-4">
        <Alert tone="info" title="Phase 1 placeholder">
          Editable application settings are not implemented yet. Configuration is supplied through
          environment variables — see <span className="font-mono text-xs">docs/ENVIRONMENT.md</span>.
        </Alert>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-900">Email delivery</h3>
          <p className="mt-1 text-sm text-slate-500">
            SMTP delivery is deliberately not implemented in Phase 1. Password reset and welcome
            messages are written to the application log and the developer outbox instead.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-sm text-slate-600">Status:</span>
            <Badge tone="amber">Log transport</Badge>
          </div>
          <p className="mt-3 text-sm text-slate-500">
            To enable real delivery, set the <span className="font-mono text-xs">SMTP_*</span>{' '}
            variables and follow <span className="font-mono text-xs">docs/SMTP.md</span>.
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-900">Your account</h3>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
            <dt className="text-slate-500">Name</dt>
            <dd className="text-slate-900">{user?.full_name}</dd>
            <dt className="text-slate-500">Email</dt>
            <dd className="text-slate-900">{user?.email}</dd>
            <dt className="text-slate-500">Roles</dt>
            <dd className="text-slate-900">
              {user?.roles.map((role) => role.name).join(', ') || 'None'}
            </dd>
          </dl>
        </section>
      </div>
    </div>
  );
}
