import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { ApiError, api } from '@/lib/api';
import type { AuditLogEntry, Page } from '@/lib/types';

const PAGE_SIZE = 25;

export function AuditTab() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await api.get<Page<AuditLogEntry>>(
        `/audit-logs?limit=${PAGE_SIZE}&offset=${offset}`,
      );
      setEntries(page.items);
      setTotal(page.total);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to load the audit log.');
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && entries.length === 0) return <LoadingState label="Loading audit log…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (entries.length === 0) {
    return <EmptyState title="No audit entries" description="Nothing has been recorded yet." />;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <caption className="sr-only">Recorded security and administrative events</caption>
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3 font-semibold">When</th>
              <th scope="col" className="px-4 py-3 font-semibold">Action</th>
              <th scope="col" className="px-4 py-3 font-semibold">Actor</th>
              <th scope="col" className="px-4 py-3 font-semibold">Target</th>
              <th scope="col" className="px-4 py-3 font-semibold">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {entries.map((entry) => (
              <tr key={entry.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">
                  {new Date(entry.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{entry.action}</td>
                <td className="px-4 py-2.5 text-slate-600">
                  {entry.actor_email ?? <span className="text-slate-400">system</span>}
                </td>
                <td className="px-4 py-2.5 text-slate-500">
                  {entry.entity_type ? `${entry.entity_type}` : '—'}
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={entry.success ? 'green' : 'red'}>
                    {entry.success ? 'ok' : 'failed'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
