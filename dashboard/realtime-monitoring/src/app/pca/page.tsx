'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';
import { FilterChips } from '@/components/FilterChips';

const fetcher = (url: string) => fetch(url).then((r) => r.json());
type SentimentFilter = 'all' | 'positive' | 'neutral' | 'negative';

export default function PcaPage() {
  const [filter, setFilter] = useState<SentimentFilter>('all');
  const { data: pcaEvals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=pca&limit=50', fetcher, { refreshInterval: 30000 });

  const filtered = pcaEvals.filter((e) => filter === 'all' || e.pca_sentiment === filter);

  const allTopics = filtered.flatMap((e) => e.pca_topics ?? []);
  const topicCounts = allTopics.reduce<Record<string, number>>((acc, t) => {
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {});
  const topTopics = Object.entries(topicCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const maxCount = topTopics[0]?.[1] ?? 1;

  const sentimentCounts = { positive: 0, neutral: 0, negative: 0 };
  for (const e of pcaEvals) {
    const s = e.pca_sentiment as keyof typeof sentimentCounts;
    if (s in sentimentCounts) sentimentCounts[s]++;
  }

  const allUnresolved = filtered.flatMap((e) => e.pca_unresolved ?? []);

  const chips = [
    { label: 'All', value: 'all' as SentimentFilter, count: pcaEvals.length },
    { label: 'Positive', value: 'positive' as SentimentFilter, count: sentimentCounts.positive },
    { label: 'Neutral', value: 'neutral' as SentimentFilter, count: sentimentCounts.neutral },
    { label: 'Negative', value: 'negative' as SentimentFilter, count: sentimentCounts.negative },
  ];

  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">Analysis</p>
        <h1 className="page-title">Post-Conversation Analysis</h1>
        <p className="page-subtitle">Topics, sentiment distribution, and unresolved questions across sessions.</p>
      </div>

      <div className="card px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <FilterChips chips={chips} active={filter} onChange={setFilter} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm mb-3">Top Topics</h3>
          {topTopics.length === 0 && <p className="text-xs text-gray-400 dark:text-gray-500">No data yet.</p>}
          <div className="space-y-2.5">
            {topTopics.map(([topic, count]) => (
              <div key={topic} className="flex items-center gap-3">
                <div className="flex-1 text-xs text-gray-700 dark:text-gray-300 truncate">{topic}</div>
                <div className="w-24 bg-gray-200 dark:bg-gray-700 rounded-sm h-1">
                  <div
                    className="bg-brand-600 dark:bg-brand-500 h-1 rounded-sm"
                    style={{ width: `${(count / maxCount) * 100}%` }}
                  />
                </div>
                <div className="text-xs text-gray-400 dark:text-gray-500 w-5 text-right font-mono tabular-nums">{count}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm mb-3">Sentiment Distribution</h3>
          <div className="space-y-2.5">
            {(['positive', 'neutral', 'negative'] as const).map((s) => (
              <div key={s} className="flex items-center gap-3">
                <div className="w-14 text-xs text-gray-500 dark:text-gray-400 capitalize">{s}</div>
                <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-sm h-1">
                  <div
                    className="bg-brand-600 dark:bg-brand-500 h-1 rounded-sm"
                    style={{ width: pcaEvals.length ? `${(sentimentCounts[s] / pcaEvals.length) * 100}%` : '0%' }}
                  />
                </div>
                <div className="text-xs text-gray-400 dark:text-gray-500 w-5 text-right font-mono tabular-nums">{sentimentCounts[s]}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Unresolved Questions</h3>
          {allUnresolved.length > 0 && (
            <span className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 px-2 py-0.5 rounded text-xs font-medium">{allUnresolved.length}</span>
          )}
        </div>
        {allUnresolved.length === 0 && <p className="text-xs text-gray-400 dark:text-gray-500">None recorded yet.</p>}
        <ul className="space-y-1.5">
          {allUnresolved.map((q, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              <span className="text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5 font-mono">{String(i + 1).padStart(2, '0')}</span>
              <span className="text-gray-700 dark:text-gray-300">{q}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
