'use client';
import useSWR from 'swr';
import KpiCards from '@/components/KpiCards';
import { ScoreBar } from '@/components/ScoreBar';
import { CopyId } from '@/components/CopyId';
import { MetricsSummary, EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function OverviewPage() {
  const { data: metrics } = useSWR<MetricsSummary>('/api/metrics/summary', fetcher, { refreshInterval: 30000 });
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=rag&limit=10', fetcher, { refreshInterval: 30000 });

  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">LLMOps</p>
        <h1 className="page-title">Overview</h1>
        <p className="page-subtitle">Real-time metrics, evaluation scores, and pipeline health.</p>
      </div>

      {metrics ? (
        <KpiCards metrics={metrics} />
      ) : (
        <div className="grid grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 h-20 animate-pulse bg-gray-50 dark:bg-gray-800" />
          ))}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Recent RAG Evaluations</h2>
            <span className="flex items-center gap-1 text-[10px] font-medium text-brand-600 dark:text-brand-400">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-pulse" />
              Live
            </span>
          </div>
          <span className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 px-2 py-0.5 rounded text-xs font-medium">{evals.length}</span>
        </div>
        <div className="grid grid-cols-5 table-header">
          <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Re-retrieved</span><span>HITL</span>
        </div>
        <div>
          {evals.length === 0 && (
            <p className="text-gray-400 dark:text-gray-500 text-sm px-4 py-6">No evaluations yet.</p>
          )}
          {evals.map((e) => (
            <div key={e.sk} className="grid grid-cols-5 table-row">
              <CopyId id={e.session_id} />
              <div>{e.rag_score ? <ScoreBar value={parseFloat(e.rag_score)} /> : <span className="text-gray-400">—</span>}</div>
              <div>{e.faithfulness ? <ScoreBar value={parseFloat(e.faithfulness)} /> : <span className="text-gray-400">—</span>}</div>
              {e.re_retrieved === 'True'
                ? <span className="badge-brand w-fit">↻ Yes</span>
                : <span className="text-gray-400 dark:text-gray-500 text-xs">No</span>
              }
              {e.hitl_flagged
                ? <span className="badge-brand w-fit">⚑ Flagged</span>
                : <span className="text-gray-400 dark:text-gray-500 text-xs">—</span>
              }
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
