import type { ReactNode } from 'react';

import type { AccessLevel, UserStatus } from '@/lib/types';

type Tone = 'neutral' | 'green' | 'amber' | 'red' | 'blue' | 'slate';

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200',
  slate: 'bg-slate-800 text-white ring-slate-700',
};

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium
        ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS_TONES: Record<UserStatus, Tone> = {
  ACTIVE: 'green',
  INACTIVE: 'neutral',
  SUSPENDED: 'red',
};

export function StatusBadge({ status }: { status: UserStatus }) {
  return <Badge tone={STATUS_TONES[status]}>{status.toLowerCase()}</Badge>;
}

const ACCESS_TONES: Record<AccessLevel, Tone> = {
  NONE: 'neutral',
  GUEST: 'blue',
  READ_ONLY: 'amber',
  COMPLETE: 'green',
};

export function AccessBadge({ level }: { level: AccessLevel }) {
  const labels: Record<AccessLevel, string> = {
    NONE: 'No access',
    GUEST: 'Guest',
    READ_ONLY: 'Read only',
    COMPLETE: 'Full access',
  };
  return <Badge tone={ACCESS_TONES[level]}>{labels[level]}</Badge>;
}
