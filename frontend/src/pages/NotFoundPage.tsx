import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="text-4xl font-bold text-slate-300">404</p>
      <h2 className="mt-2 text-lg font-semibold text-slate-900">Page not found</h2>
      <p className="mt-1 text-sm text-slate-500">
        The page you are looking for does not exist or you do not have access to it.
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
