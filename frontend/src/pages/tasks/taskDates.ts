/**
 * Date handling for the quick filters.
 *
 * A task's date is a calendar date, not an instant: the API stores and filters
 * a plain `DATE`. "Today" therefore has to mean today *where the reader is*, so
 * these helpers work in local time and format with the local calendar fields.
 * `toISOString()` is deliberately avoided -- it converts to UTC first, which
 * rolls the date over for anyone east or west of Greenwich.
 */

export type DateFilter = 'all' | 'today' | 'yesterday' | 'custom';

/** `YYYY-MM-DD` for a date, using its local calendar fields. */
export function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function today(): string {
  return toIsoDate(new Date());
}

export function yesterday(): string {
  const date = new Date();
  date.setDate(date.getDate() - 1);
  return toIsoDate(date);
}

/**
 * The inclusive day range a filter selects, or `null` for no date filtering.
 *
 * Every quick filter picks a single day, so both ends are the same date; the
 * API takes a range so the shape stays useful if a span is ever needed.
 */
export function rangeFor(filter: DateFilter, customDate: string): { from: string; to: string } | null {
  switch (filter) {
    case 'today': {
      const day = today();
      return { from: day, to: day };
    }
    case 'yesterday': {
      const day = yesterday();
      return { from: day, to: day };
    }
    case 'custom':
      return customDate ? { from: customDate, to: customDate } : null;
    default:
      return null;
  }
}

/** Render an API date (`YYYY-MM-DD`) without letting the parser assume UTC. */
export function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString();
}
