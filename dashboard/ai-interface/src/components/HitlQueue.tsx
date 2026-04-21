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
    return <p className="text-gray-500 text-sm p-6">No items in queue.</p>;
  }

  return (
    <div className="divide-y divide-gray-800">
      {items.map((item) => (
        <div key={item.sk} className="p-4">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setExpandedId(expandedId === item.sk ? null : item.sk)}
          >
            <div className="space-y-0.5">
              <p className="text-sm font-mono text-blue-400">{item.session_id.slice(0, 24)}…</p>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className="px-2 py-0.5 bg-gray-800 rounded">{item.trigger}</span>
                {item.rag_score && <span>RAG: <span className="text-red-400">{parseFloat(item.rag_score).toFixed(2)}</span></span>}
                {item.llm_judge_score && <span>Judge: <span className="text-red-400">{parseFloat(item.llm_judge_score).toFixed(2)}</span></span>}
                <span>{new Date(item.created_at).toLocaleString()}</span>
              </div>
            </div>
            <span className="text-gray-600 text-xs">{expandedId === item.sk ? '▲' : '▼'}</span>
          </div>
          {expandedId === item.sk && (
            <div className="mt-3 space-y-3">
              <div className="bg-gray-900 border border-gray-700 rounded p-3 text-xs text-gray-400 leading-relaxed max-h-40 overflow-y-auto">
                {item.conversation_summary}
              </div>
              <textarea
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                placeholder="Type your human response here…"
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none h-24"
              />
              <button
                onClick={() => handleSubmit(item.sk)}
                disabled={submitting || !response.trim()}
                className="px-4 py-2 text-xs bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-white transition-colors"
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
