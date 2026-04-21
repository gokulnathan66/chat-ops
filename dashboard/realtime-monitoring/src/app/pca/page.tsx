'use client';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function PcaPage() {
  const { data: pcaEvals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=pca&limit=50', fetcher, { refreshInterval: 30000 });

  const allTopics = pcaEvals.flatMap((e) => e.pca_topics ?? []);
  const topicCounts = allTopics.reduce<Record<string, number>>((acc, t) => {
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {});
  const topTopics = Object.entries(topicCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const sentimentCounts = { positive: 0, neutral: 0, negative: 0 };
  for (const e of pcaEvals) {
    const s = e.pca_sentiment as keyof typeof sentimentCounts;
    if (s in sentimentCounts) sentimentCounts[s]++;
  }

  const allUnresolved = pcaEvals.flatMap((e) => e.pca_unresolved ?? []);

  return (
    <div className="max-w-4xl space-y-8">
      <h2 className="text-lg font-semibold">Post-Conversation Analysis</h2>
      <div className="grid grid-cols-2 gap-6">
        <div className="border border-gray-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-400">Top Topics</h3>
          {topTopics.length === 0 && <p className="text-xs text-gray-600">No data yet.</p>}
          {topTopics.map(([topic, count]) => (
            <div key={topic} className="flex items-center gap-3">
              <div className="flex-1 text-xs text-gray-300 truncate">{topic}</div>
              <div className="w-24 bg-gray-800 rounded-full h-1.5">
                <div
                  className="bg-purple-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, (count / pcaEvals.length) * 100)}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 w-6 text-right">{count}</div>
            </div>
          ))}
        </div>
        <div className="border border-gray-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-400">Sentiment Distribution</h3>
          {(['positive', 'neutral', 'negative'] as const).map((s) => (
            <div key={s} className="flex items-center gap-3">
              <div className="w-16 text-xs text-gray-400 capitalize">{s}</div>
              <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${s === 'positive' ? 'bg-green-500' : s === 'negative' ? 'bg-red-500' : 'bg-gray-500'}`}
                  style={{ width: pcaEvals.length ? `${(sentimentCounts[s] / pcaEvals.length) * 100}%` : '0%' }}
                />
              </div>
              <div className="text-xs text-gray-500 w-6 text-right">{sentimentCounts[s]}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-3">Unresolved Questions</h3>
        {allUnresolved.length === 0 && <p className="text-xs text-gray-600">None recorded yet.</p>}
        <ul className="space-y-1">
          {allUnresolved.map((q, i) => (
            <li key={i} className="text-xs text-red-300 flex items-start gap-2">
              <span className="text-red-600 mt-0.5">❓</span>{q}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
