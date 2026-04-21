'use client';
import useSWR from 'swr';
import HitlQueue from '@/components/HitlQueue';
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
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div>
        <h2 className="text-lg font-semibold mb-1">Pending</h2>
        <p className="text-xs text-gray-500 mb-4">Sessions flagged by evaluators or escalated by users.</p>
        <div className="border border-gray-800 rounded-lg">
          <HitlQueue items={pending} onResolved={() => mutatePending()} />
        </div>
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-1 text-gray-500">Resolved</h2>
        <div className="border border-gray-800 rounded-lg divide-y divide-gray-800">
          {resolved.length === 0 && <p className="text-gray-600 text-sm p-4">None resolved yet.</p>}
          {resolved.map((item) => (
            <div key={item.sk} className="p-4 text-xs text-gray-500">
              <span className="font-mono text-gray-400">{item.session_id.slice(0, 24)}…</span>
              <span className="ml-3">{item.human_response?.slice(0, 80)}…</span>
              <span className="ml-3 text-gray-600">{item.resolved_at ? new Date(item.resolved_at).toLocaleString() : ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
