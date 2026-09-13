/**
 * Chart colours, drawn from the palette the rest of the application already
 * uses so a chart never introduces a colour the UI has not seen before.
 *
 * Status hues match the badges T1 renders, so a status reads the same in the
 * table and in the charts.
 */

import type { TaskStatus } from '@/lib/types';

export const STATUS_COLORS: Record<TaskStatus, string> = {
  Created: '#3465f7', // brand-500
  Inprogress: '#f59e0b', // amber-500
  Onhold: '#94a3b8', // slate-400
  Completed: '#10b981', // emerald-500
  Triage: '#ef4444', // red-500
};

/** Service bars are one hue on purpose: the length is the message, not the colour. */
export const SERIES_PRIMARY = '#3465f7'; // brand-500
export const SERIES_SECONDARY = '#10b981'; // emerald-500

export const AXIS = '#94a3b8'; // slate-400
export const GRID = '#e2e8f0'; // slate-200
