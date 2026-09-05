import { Link } from 'react-router-dom';

export function ForbiddenPage({ moduleName }: { moduleName?: string }) {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="text-4xl" aria-hidden="true">
        🔒
      </p>
      <h2 className="mt-3 text-lg font-semibold text-slate-900">Access denied</h2>
      <p className="mt-1 text-sm text-slate-500">
        You do not have permission to view{' '}
        {moduleName ? <span className="font-medium">{moduleName}</span> : 'this page'}. If you
        believe this is a mistake, contact an administrator.
      </p>
      <Link
        to="/dashboard"
        className="mt-6 inline-block text-sm font-medium text-brand-700 hover:underline"
      >
        ← Back to dashboard
      </Link>
    </div>
  );
}
