import type { ReactNode } from 'react';

/** Loading, empty and error states -- used consistently across every page. */

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <span role="status" aria-label={label} className="inline-flex items-center">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600"
      />
    </span>
  );
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-500">
      <Spinner />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed
                    border-slate-300 bg-white py-16 text-center">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      {description && <p className="max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border
                    border-red-200 bg-red-50 py-12 text-center">
      <p className="text-sm font-semibold text-red-800">Something went wrong</p>
      <p className="max-w-md text-sm text-red-700">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-sm font-medium text-red-800 underline underline-offset-2"
        >
          Try again
        </button>
      )}
    </div>
  );
}
