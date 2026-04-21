'use client';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function score(val: string | undefined) {
  if (!val) return <span className="text-gray-600">—</span>;
  const n = parseFloat(val);
  const cls = n >= 0.8 ? 'text-green-400' : n >= 0.6 ? 'text-yellow-400' : 'text-red-400';
  return <span className={cls}>{n.toFixed(3)}</span>;
}

export default function EvalsPage() {
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=rag&limit=100', fetcher, { refreshInterval: 30000 });

  return (
    <div className="max-w-6xl space-y-4">
      <h2 className="text-lg font-semibold">RAG Evaluations</h2>
      <div className="border border-gray-800 rounded-lg overflow-auto">
        <div className="grid grid-cols-6 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900 min-w-[700px]">
          <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Relevance</span><span>Re-retrieved</span><span>HITL</span>
        </div>
        {evals.length === 0 && <p className="text-gray-600 text-sm p-4">No evaluations yet.</p>}
        {evals.map((e) => (
          <div key={e.sk} className="grid grid-cols-6 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900 min-w-[700px]">
            <span className="font-mono text-blue-400 truncate">{e.session_id.slice(0, 16)}…</span>
            {score(e.rag_score)}
            {score(e.faithfulness)}
            {score(e.relevance)}
            <span className={e.re_retrieved === 'True' ? 'text-yellow-400' : 'text-gray-600'}>
              {e.re_retrieved === 'True' ? 'Yes' : 'No'}
            </span>
            <span className={e.hitl_flagged ? 'text-red-400 font-semibold' : 'text-gray-600'}>
              {e.hitl_flagged ? '⚑' : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
