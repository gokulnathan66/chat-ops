import { MetricsSummary } from '@/lib/api';

function KpiCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

export default function KpiCards({ metrics }: { metrics: MetricsSummary }) {
  return (
    <div className="grid grid-cols-5 gap-4">
      <KpiCard label="Golden Pass Rate" value={`${metrics.golden_pass_rate_pct}%`} color="text-green-400" />
      <KpiCard label="Avg RAG Score" value={metrics.avg_rag_score.toFixed(2)} color="text-blue-400" />
      <KpiCard label="Avg Faithfulness" value={metrics.avg_faithfulness.toFixed(2)} color="text-purple-400" />
      <KpiCard label="Cost Today" value={`$${metrics.cost_today_usd.toFixed(4)}`} color="text-yellow-400" />
      <KpiCard label="HITL Pending" value={String(metrics.hitl_pending)} color={metrics.hitl_pending > 0 ? 'text-red-400' : 'text-gray-400'} />
    </div>
  );
}
