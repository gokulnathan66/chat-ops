'use client';
import useSWR from 'swr';
import HitlQueue from '@/components/HitlQueue';
import { CopyId } from '@/components/CopyId';
import { HitlItem } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function HitlPage() {
  const { data: pending = [], mutate: mutatePending } = useSWR<HitlItem[]>(
    '/api/hitl?status=pending', fetcher, { refreshInterval: 15000 }
  );
  const { data: resolved = [] } = useSWR<HitlItem[]>(
    '/api/hitl?status=resolved', fetcher, { refreshInterval: 30000 }
  );

  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">Operations</p>
        <h1 className="page-title">HITL Queue</h1>
        <p className="page-subtitle">Sessions flagged by evaluators for human review and response.</p>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Pending</h2>
            {pending.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] font-medium text-brand-600 dark:text-brand-400">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-pulse" />
                Live
              </span>
            )}
          </div>
          {pending.length > 0 && (
            <span className="badge-brand">{pending.length}</span>
          )}
        </div>
        <HitlQueue items={pending} onResolved={() => mutatePending()} />
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="font-semibold text-gray-500 dark:text-gray-400 text-sm">Resolved</h2>
          <span className="badge">{resolved.length}</span>
        </div>
        <div>
          {resolved.length === 0 && (
            <p className="text-gray-400 dark:text-gray-500 text-sm px-4 py-6">None resolved yet.</p>
          )}
          {resolved.map((item) => (
            <div key={item.sk} className="px-4 py-2.5 flex items-center gap-4 border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
              <CopyId id={item.session_id} />
              <span className="flex-1 text-xs text-gray-500 dark:text-gray-400 truncate">{item.human_response?.slice(0, 80)}</span>
              <span className="text-[10px] text-gray-400 dark:text-gray-500 flex-shrink-0 font-mono">{item.resolved_at ? new Date(item.resolved_at).toLocaleString() : ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
