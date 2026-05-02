'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';
import { ScoreBar } from '@/components/ScoreBar';
import { FilterChips } from '@/components/FilterChips';
import { CopyId } from '@/components/CopyId';

const fetcher = (url: string) => fetch(url).then((r) => r.json());
type Filter = 'all' | 'hitl' | 'reranked' | 'low';

export default function EvalsPage() {
  const [filter, setFilter] = useState<Filter>('all');
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=rag&limit=100', fetcher, { refreshInterval: 30000 });

  const filtered = evals.filter((e) => {
    if (filter === 'hitl') return e.hitl_flagged;
    if (filter === 'reranked') return e.re_retrieved === 'True';
    if (filter === 'low') return e.rag_score ? parseFloat(e.rag_score) < 0.6 : false;
    return true;
  });

  const chips = [
    { label: 'All', value: 'all' as Filter, count: evals.length },
    { label: 'HITL Flagged', value: 'hitl' as Filter, count: evals.filter(e => e.hitl_flagged).length },
    { label: 'Re-retrieved', value: 'reranked' as Filter, count: evals.filter(e => e.re_retrieved === 'True').length },
    { label: 'Low Score', value: 'low' as Filter, count: evals.filter(e => e.rag_score ? parseFloat(e.rag_score) < 0.6 : false).length },
  ];

  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">Evaluation</p>
        <h1 className="page-title">RAG Evaluations</h1>
        <p className="page-subtitle">Session-level retrieval quality, faithfulness, and HITL flag status.</p>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30">
          <FilterChips chips={chips} active={filter} onChange={setFilter} />
          <div className="flex items-center gap-1.5 text-[10px] font-medium text-brand-600 dark:text-brand-400 flex-shrink-0 ml-4">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-pulse" />
            Live
          </div>
        </div>
        <div className="overflow-x-auto">
          <div className="grid grid-cols-6 table-header min-w-[780px]">
            <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Relevance</span><span>Re-retrieved</span><span>HITL</span>
          </div>
          <div>
            {filtered.length === 0 && (
              <p className="text-gray-400 dark:text-gray-500 text-sm px-4 py-6">No evaluations match this filter.</p>
            )}
            {filtered.map((e) => (
              <div key={e.sk} className="grid grid-cols-6 table-row min-w-[780px]">
                <CopyId id={e.session_id} />
                <div>{e.rag_score ? <ScoreBar value={parseFloat(e.rag_score)} /> : <span className="text-gray-400">—</span>}</div>
                <div>{e.faithfulness ? <ScoreBar value={parseFloat(e.faithfulness)} /> : <span className="text-gray-400">—</span>}</div>
                <div>{e.relevance ? <ScoreBar value={parseFloat(e.relevance)} /> : <span className="text-gray-400">—</span>}</div>
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
    </div>
  );
}
