/**
 * Two-series line chart for activity over time.
 *
 * SVG with a `viewBox` and no intrinsic size, so it scales to its container.
 * Coordinates are computed in a fixed internal space and the browser handles
 * the rest -- no resize observer, no re-render on window size.
 *
 * A transparent overlay tracks the pointer and snaps to the nearest day, which
 * is far easier to hit than the 3px line itself.
 */

import { useMemo, useState } from 'react';

import { AXIS, GRID, SERIES_PRIMARY, SERIES_SECONDARY } from './palette';

export interface LinePoint {
  date: string;
  created: number;
  completed: number;
}

const WIDTH = 720;
const HEIGHT = 220;
const PAD = { top: 12, right: 12, bottom: 26, left: 32 };

/** `YYYY-MM-DD` → short label, parsed as local time (not UTC). */
function shortDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

export function LineChart({
  points,
  emptyLabel = 'No activity in this period',
}: {
  points: LinePoint[];
  emptyLabel?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    const peak = Math.max(...points.flatMap((p) => [p.created, p.completed]), 1);
    // Round the axis up to something a reader can divide by eye.
    const ceiling = Math.max(4, Math.ceil(peak / 4) * 4);
    const plotWidth = WIDTH - PAD.left - PAD.right;
    const plotHeight = HEIGHT - PAD.top - PAD.bottom;

    const x = (index: number) =>
      PAD.left + (points.length <= 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
    const y = (value: number) => PAD.top + plotHeight - (value / ceiling) * plotHeight;

    const path = (key: 'created' | 'completed') =>
      points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point[key])}`).join(' ');

    return { ceiling, x, y, path, plotHeight };
  }, [points]);

  if (points.length === 0) {
    return <p className="py-10 text-center text-sm text-slate-500">{emptyLabel}</p>;
  }

  const totals = points.reduce(
    (sum, point) => ({ created: sum.created + point.created, completed: sum.completed + point.completed }),
    { created: 0, completed: 0 },
  );
  if (totals.created === 0 && totals.completed === 0) {
    return <p className="py-10 text-center text-sm text-slate-500">{emptyLabel}</p>;
  }

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => Math.round(geometry.ceiling * fraction));
  // At most ~7 date labels, however wide the window.
  const labelEvery = Math.max(1, Math.ceil(points.length / 7));
  const active = hover === null ? null : points[hover];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs">
        <span className="inline-flex items-center gap-1.5 text-slate-600">
          <span aria-hidden="true" className="h-0.5 w-4 rounded" style={{ backgroundColor: SERIES_PRIMARY }} />
          Tasks dated ({totals.created})
        </span>
        <span className="inline-flex items-center gap-1.5 text-slate-600">
          <span aria-hidden="true" className="h-0.5 w-4 rounded" style={{ backgroundColor: SERIES_SECONDARY }} />
          Of those, completed ({totals.completed})
        </span>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full"
          role="img"
          aria-label={`Task activity: ${totals.created} tasks over ${points.length} days`}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={geometry.y(tick)}
                y2={geometry.y(tick)}
                stroke={GRID}
                strokeWidth={1}
              />
              <text x={PAD.left - 6} y={geometry.y(tick) + 3} textAnchor="end" fontSize={9} fill={AXIS}>
                {tick}
              </text>
            </g>
          ))}

          {points.map((point, index) =>
            index % labelEvery === 0 ? (
              <text
                key={point.date}
                x={geometry.x(index)}
                y={HEIGHT - 8}
                textAnchor="middle"
                fontSize={9}
                fill={AXIS}
              >
                {shortDate(point.date)}
              </text>
            ) : null,
          )}

          <path d={geometry.path('created')} fill="none" stroke={SERIES_PRIMARY} strokeWidth={2}
                strokeLinejoin="round" strokeLinecap="round" />
          <path d={geometry.path('completed')} fill="none" stroke={SERIES_SECONDARY} strokeWidth={2}
                strokeLinejoin="round" strokeLinecap="round" />

          {hover !== null && (
            <line
              x1={geometry.x(hover)}
              x2={geometry.x(hover)}
              y1={PAD.top}
              y2={PAD.top + geometry.plotHeight}
              stroke={AXIS}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          )}

          {points.map((point, index) => (
            <g key={point.date}>
              <circle cx={geometry.x(index)} cy={geometry.y(point.created)}
                      r={hover === index ? 4 : 2.5} fill={SERIES_PRIMARY} />
              <circle cx={geometry.x(index)} cy={geometry.y(point.completed)}
                      r={hover === index ? 4 : 2.5} fill={SERIES_SECONDARY} />
            </g>
          ))}

          {/* Pointer target: one full-height band per day, so the nearest point
              is picked without the reader having to hit the line. */}
          {points.map((point, index) => {
            const band = (WIDTH - PAD.left - PAD.right) / Math.max(points.length, 1);
            return (
              <rect
                key={`hit-${point.date}`}
                x={geometry.x(index) - band / 2}
                y={PAD.top}
                width={band}
                height={geometry.plotHeight}
                fill="transparent"
                onMouseEnter={() => setHover(index)}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}
        </svg>

        {active && (
          <div
            className="pointer-events-none absolute top-0 rounded-md border border-slate-200
                       bg-white px-2.5 py-1.5 text-xs shadow-md"
            style={{
              left: `${(geometry.x(hover!) / WIDTH) * 100}%`,
              transform: 'translateX(-50%)',
            }}
          >
            <p className="font-medium text-slate-900">{shortDate(active.date)}</p>
            <p className="text-slate-600">
              <span style={{ color: SERIES_PRIMARY }}>●</span> {active.created} dated
            </p>
            <p className="text-slate-600">
              <span style={{ color: SERIES_SECONDARY }}>●</span> {active.completed} completed
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
