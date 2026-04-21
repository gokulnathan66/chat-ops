'use client';
import useSWR from 'swr';
import KpiCards from '@/components/KpiCards';
import { MetricsSummary, EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function scoreColor(score: string | undefined) {
  if (!score) return 'text-gray-500';
  const n = parseFloat(score);
  if (n >= 0.8) return 'text-green-400';
  if (n >= 0.6) return 'text-yellow-400';
  return 'text-red-400';
}

export default function OverviewPage() {
  const { data: metrics } = useSWR<MetricsSummary>('/api/metrics/summary', fetcher, { refreshInterval: 30000 });
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=rag&limit=10', fetcher, { refreshInterval: 30000 });
  const { data: pcaEvals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=pca&limit=1', fetcher, { refreshInterval: 30000 });

  const latestPca = pcaEvals[0];

  return (
    <div className="space-y-8 max-w-6xl">
      {metrics ? <KpiCards metrics={metrics} /> : (
        <div className="grid grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-20 animate-pulse" />
          ))}
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Recent RAG Evaluations</h2>
        <div className="border border-gray-800 rounded-lg overflow-hidden">
          <div className="grid grid-cols-5 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900">
            <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Re-retrieved</span><span>HITL</span>
          </div>
          {evals.length === 0 && <p className="text-gray-600 text-sm p-4">No evaluations yet.</p>}
          {evals.map((e) => (
            <div key={e.sk} className="grid grid-cols-5 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900">
              <span className="font-mono text-blue-400 truncate">{e.session_id.slice(0, 18)}…</span>
              <span className={scoreColor(e.rag_score)}>{e.rag_score ? parseFloat(e.rag_score).toFixed(2) : '—'}</span>
              <span className={scoreColor(e.faithfulness)}>{e.faithfulness ? parseFloat(e.faithfulness).toFixed(2) : '—'}</span>
              <span className={e.re_retrieved === 'True' ? 'text-yellow-400' : 'text-gray-500'}>{e.re_retrieved === 'True' ? 'Yes' : 'No'}</span>
              <span className={e.hitl_flagged ? 'text-red-400 font-semibold' : 'text-gray-600'}>{e.hitl_flagged ? '⚑ Flagged' : '—'}</span>
            </div>
          ))}
        </div>
      </div>

      {latestPca && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Latest PCA</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            {latestPca.pca_topics?.map((t) => (
              <span key={t} className="bg-purple-900 text-purple-300 px-3 py-1 rounded-full">{t}</span>
            ))}
            <span className={`px-3 py-1 rounded-full font-medium ${
              latestPca.pca_sentiment === 'positive' ? 'bg-green-900 text-green-300' :
              latestPca.pca_sentiment === 'negative' ? 'bg-red-900 text-red-300' :
              'bg-gray-800 text-gray-400'
            }`}>
              {latestPca.pca_sentiment}
            </span>
            {latestPca.pca_unresolved?.map((q) => (
              <span key={q} className="bg-red-950 text-red-400 px-3 py-1 rounded-full">❓ {q}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
