'use client';
import useSWR from 'swr';
import { GoldenResult } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function GoldenPage() {
  const { data: results = [] } = useSWR<GoldenResult[]>('/api/golden-results', fetcher, { refreshInterval: 60000 });

  const runs = Array.from(new Set(results.map((r) => r.run_id)));
  const passRate = results.length > 0
    ? Math.round((results.filter((r) => r.pass).length / results.length) * 100)
    : 0;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-6">
        <h2 className="text-lg font-semibold">Golden Dataset</h2>
        <span className="text-sm text-gray-500">{runs.length} run(s) · Overall pass rate:
          <span className={`ml-1 font-bold ${passRate >= 80 ? 'text-green-400' : passRate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
            {passRate}%
          </span>
        </span>
      </div>
      <div className="border border-gray-800 rounded-lg overflow-auto">
        <div className="grid grid-cols-5 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900 min-w-[700px]">
          <span className="col-span-2">Question</span><span>Judge Score</span><span>Run</span><span>Pass</span>
        </div>
        {results.length === 0 && <p className="text-gray-600 text-sm p-4">No golden results yet.</p>}
        {results.map((r) => (
          <div key={`${r.run_id}-${r.question_id}`} className="grid grid-cols-5 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900 min-w-[700px]">
            <span className="col-span-2 text-gray-300 truncate">{r.question}</span>
            <span className={parseFloat(r.llm_judge_score) >= 0.7 ? 'text-green-400' : 'text-red-400'}>
              {parseFloat(r.llm_judge_score).toFixed(2)}
            </span>
            <span className="font-mono text-gray-500 text-[10px]">{r.run_id.slice(0, 12)}…</span>
            <span className={r.pass ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
              {r.pass ? '✓ Pass' : '✗ Fail'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
