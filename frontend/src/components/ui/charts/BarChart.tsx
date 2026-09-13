/**
 * Horizontal bar chart.
 *
 * Built from layout elements rather than SVG: horizontal bars are a list of
 * rows, and expressing them that way makes the chart responsive for free,
 * keeps the labels selectable, and lets a row be a real `<button>` when it
 * navigates somewhere.
 */

import { SERIES_PRIMARY } from './palette';

export interface BarDatum {
  label: string;
  value: number;
  /** Rendered instead of the bare count, e.g. "21 tasks". */
  title?: string;
  onClick?: () => void;
}

export function BarChart({ data, emptyLabel = 'No data' }: { data: BarDatum[]; emptyLabel?: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return <p className="py-10 text-center text-sm text-slate-500">{emptyLabel}</p>;
  }

  return (
    <ul className="flex flex-col gap-2.5">
      {data.map((datum) => {
        const percent = (datum.value / max) * 100;
        const share = total ? Math.round((datum.value / total) * 100) : 0;
        const label = (
          <>
            <span className="w-32 shrink-0 truncate text-xs font-medium text-slate-600 sm:w-40">
              {datum.label}
            </span>
            <span className="relative h-6 min-w-0 flex-1 overflow-hidden rounded bg-slate-100">
              <span
                className="absolute inset-y-0 left-0 rounded transition-[width] duration-500 ease-out"
                style={{ width: `${percent}%`, backgroundColor: SERIES_PRIMARY }}
              />
            </span>
            <span className="w-10 shrink-0 text-right text-xs font-semibold tabular-nums text-slate-700">
              {datum.value}
            </span>
          </>
        );

        const title = datum.title ?? `${datum.label}: ${datum.value} (${share}%)`;

        return (
          <li key={datum.label}>
            {datum.onClick ? (
              <button
                type="button"
                onClick={datum.onClick}
                title={title}
                className="flex w-full items-center gap-3 rounded px-1 py-0.5 text-left
                           hover:bg-slate-50 focus-visible:bg-slate-50"
              >
                {label}
              </button>
            ) : (
              <div className="flex items-center gap-3 px-1 py-0.5" title={title}>
                {label}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
