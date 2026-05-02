'use client';
import { useState } from 'react';
import { HitlItem, respondHitl } from '@/lib/api';

interface Props {
  items: HitlItem[];
  onResolved: () => void;
}

export default function HitlQueue({ items, onResolved }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [response, setResponse] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (queueId: string) => {
    if (!response.trim()) return;
    setSubmitting(true);
    try {
      await respondHitl(queueId, response);
      setResponse('');
      setExpandedId(null);
      onResolved();
    } finally {
      setSubmitting(false);
    }
  };

  if (items.length === 0) {
    return <p className="text-gray-400 dark:text-gray-500 text-sm p-5">No items in queue.</p>;
  }

  return (
    <div>
      {items.map((item) => (
        <div key={item.sk} className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
          <div
            className="flex items-center justify-between px-4 py-3 cursor-pointer"
            onClick={() => setExpandedId(expandedId === item.sk ? null : item.sk)}
          >
            <div className="space-y-0.5">
              <p className="text-xs font-mono text-brand-600 dark:text-brand-400">{item.session_id.slice(0, 24)}…</p>
              <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400">
                <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded text-[10px] font-medium border border-gray-200 dark:border-gray-700">{item.trigger}</span>
                {item.rag_score && (
                  <span>RAG: <span className="text-gray-700 dark:text-gray-300 font-mono">{parseFloat(item.rag_score).toFixed(2)}</span></span>
                )}
                {item.llm_judge_score && (
                  <span>Judge: <span className="text-gray-700 dark:text-gray-300 font-mono">{parseFloat(item.llm_judge_score).toFixed(2)}</span></span>
                )}
                <span className="text-gray-400 dark:text-gray-500">{new Date(item.created_at).toLocaleString()}</span>
              </div>
            </div>
            <span className="text-gray-400 dark:text-gray-500 text-[10px] ml-4">{expandedId === item.sk ? '▲' : '▼'}</span>
          </div>
          {expandedId === item.sk && (
            <div className="px-4 pb-4 space-y-3 animate-fade-in">
              <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md p-3 text-xs text-gray-600 dark:text-gray-400 leading-relaxed max-h-40 overflow-y-auto">
                {item.conversation_summary}
              </div>
              <textarea
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                placeholder="Type your human response here…"
                className="input resize-none h-24"
              />
              <button
                onClick={() => handleSubmit(item.sk)}
                disabled={submitting || !response.trim()}
                className="btn-primary"
              >
                {submitting ? 'Submitting…' : 'Submit Response'}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
