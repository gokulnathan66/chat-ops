import { MetricsSummary } from '@/lib/api';

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4">
      <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">{label}</p>
      <p className="text-2xl font-bold tracking-tight text-gray-900 dark:text-gray-100 tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function KpiCards({ metrics }: { metrics: MetricsSummary }) {
  return (
    <div className="grid grid-cols-5 gap-3">
      <KpiCard label="Golden Pass Rate" value={`${metrics.golden_pass_rate_pct}%`} sub="regression suite" />
      <KpiCard label="Avg RAG Score" value={metrics.avg_rag_score.toFixed(2)} sub="cosine similarity" />
      <KpiCard label="Avg Faithfulness" value={metrics.avg_faithfulness.toFixed(2)} sub="LLM judge" />
      <KpiCard label="Cost Today" value={`$${metrics.cost_today_usd.toFixed(4)}`} sub="USD" />
      <KpiCard label="HITL Pending" value={String(metrics.hitl_pending)} sub="needs review" />
    </div>
  );
}
