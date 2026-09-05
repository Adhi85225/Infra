import type { ReactNode } from 'react';

type Tone = 'error' | 'success' | 'info' | 'warning';

const TONES: Record<Tone, { wrapper: string; icon: string }> = {
  error: { wrapper: 'bg-red-50 text-red-800 border-red-200', icon: '⚠' },
  success: { wrapper: 'bg-emerald-50 text-emerald-800 border-emerald-200', icon: '✓' },
  info: { wrapper: 'bg-blue-50 text-blue-800 border-blue-200', icon: 'ℹ' },
  warning: { wrapper: 'bg-amber-50 text-amber-900 border-amber-200', icon: '⚠' },
};

export function Alert({
  tone = 'info',
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
}) {
  const style = TONES[tone];
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`flex gap-3 rounded-md border px-4 py-3 text-sm ${style.wrapper}`}
    >
      <span aria-hidden="true" className="mt-0.5 font-bold">
        {style.icon}
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-1' : ''}>{children}</div>}
      </div>
    </div>
  );
}
