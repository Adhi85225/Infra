import type { ReactNode } from 'react';

/** Centred card used by every unauthenticated page. */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mb-2 text-3xl" aria-hidden="true">
            🌐
          </div>
          <h1 className="text-xl font-semibold text-slate-900">Global Infrastructure</h1>
          <p className="text-sm text-slate-500">Internal helper tools</p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mb-5 mt-1 text-sm text-slate-500">{subtitle}</p>}
          {!subtitle && <div className="mb-5" />}
          {children}
        </div>
      </div>
    </div>
  );
}
