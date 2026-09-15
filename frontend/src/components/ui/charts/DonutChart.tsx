/**
 * Donut chart with a legend.
 *
 * Segments are arcs drawn with `stroke-dasharray` on one circle -- no path
 * maths, and the browser antialiases the joins for us. The SVG carries a
 * `viewBox` and no fixed size, so it scales with its container.
 *
 * Flat by design: no 3D, no gradients. The reader is comparing five
 * quantities, and shading distorts that.
 */

import { useState } from 'react';

export interface DonutSlice {
  label: string;
  value: number;
  color: string;
  onClick?: () => void;
}

const SIZE = 160;
const STROKE = 26;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function DonutChart({
  slices,
  centerLabel,
  emptyLabel = 'No data',
}: {
  slices: DonutSlice[];
  centerLabel: string;
  emptyLabel?: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  if (total === 0) {
    return <p className="py-10 text-center text-sm text-slate-500">{emptyLabel}</p>;
  }

  let offset = 0;
  const arcs = slices
    .filter((slice) => slice.value > 0)
    .map((slice) => {
      const length = (slice.value / total) * CIRCUMFERENCE;
      const arc = { ...slice, length, offset };
      offset += length;
      return arc;
    });

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:justify-center">
      <div className="relative w-40 shrink-0">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full" role="img"
             aria-label={`${centerLabel}: ${total} in total`}>
          {/* Rotated so the first segment starts at twelve o'clock. */}
          <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
            {arcs.map((arc) => (
              <circle
                key={arc.label}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke={arc.color}
                strokeWidth={active === arc.label ? STROKE + 5 : STROKE}
                strokeDasharray={`${arc.length} ${CIRCUMFERENCE - arc.length}`}
                strokeDashoffset={-arc.offset}
                className="cursor-pointer transition-[stroke-width] duration-150"
                onMouseEnter={() => setActive(arc.label)}
                onMouseLeave={() => setActive(null)}
                onClick={arc.onClick}
              >
                <title>{`${arc.label}: ${arc.value} (${Math.round((arc.value / total) * 100)}%)`}</title>
              </circle>
            ))}
          </g>
        </svg>

        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums text-slate-900">
            {active ? slices.find((s) => s.label === active)?.value : total}
          </span>
          <span className="max-w-[6rem] text-center text-[11px] leading-tight text-slate-500">
            {active ?? centerLabel}
          </span>
        </div>
      </div>

      <ul className="flex w-full min-w-0 flex-col gap-1.5 sm:w-auto">
        {slices.map((slice) => {
          const share = Math.round((slice.value / total) * 100);
          const content = (
            <>
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ backgroundColor: slice.color }}
              />
              <span className="min-w-0 flex-1 truncate text-slate-600">{slice.label}</span>
              <span className="tabular-nums font-semibold text-slate-800">{slice.value}</span>
              <span className="w-9 text-right tabular-nums text-slate-400">{share}%</span>
            </>
          );
          return (
            <li key={slice.label}>
              {slice.onClick ? (
                <button
                  type="button"
                  onClick={slice.onClick}
                  onMouseEnter={() => setActive(slice.label)}
                  onMouseLeave={() => setActive(null)}
                  className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left text-xs
                             hover:bg-slate-50 focus-visible:bg-slate-50"
                >
                  {content}
                </button>
              ) : (
                <div className="flex items-center gap-2 px-1.5 py-1 text-xs">{content}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
