'use client';
import { useState } from 'react';
import { Conversation } from '@/lib/api';

interface Props {
  conversation: Conversation;
  onEscalate: () => void;
}

export default function ChatThread({ conversation, onEscalate }: Props) {
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  const toggleDocs = (sk: string) => {
    setExpandedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(sk)) next.delete(sk);
      else next.add(sk);
      return next;
    });
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
        <span className="text-sm font-mono text-gray-400">
          {conversation.metadata.session_id}
        </span>
        <button
          onClick={onEscalate}
          className="text-xs px-3 py-1 rounded border border-red-700 text-red-400 hover:bg-red-900 transition-colors"
        >
          Escalate to Human
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {conversation.turns.map((turn) => (
          <div key={turn.sk} className="space-y-2">
            <div className="bg-gray-800 rounded-lg px-4 py-3">
              <p className="text-[10px] text-gray-500 mb-1">User</p>
              <p className="text-sm text-gray-100">{turn.user_query}</p>
            </div>
            <div className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-3">
              <div className="flex items-center gap-3 mb-1">
                <p className="text-[10px] text-gray-500">
                  AI · {turn.route} · {Math.round(turn.latency_ms)}ms ·{' '}
                  {turn.token_usage.input + turn.token_usage.output} tokens
                </p>
              </div>
              <p className="text-sm text-gray-200">{turn.ai_response}</p>
              {turn.retrieved_docs.length > 0 && (
                <div className="mt-2">
                  <button
                    onClick={() => toggleDocs(turn.sk)}
                    className="text-[10px] text-blue-400 hover:underline"
                  >
                    {expandedDocs.has(turn.sk) ? '▼' : '▶'} {turn.retrieved_docs.length} retrieved doc(s)
                  </button>
                  {expandedDocs.has(turn.sk) && (
                    <div className="mt-1 space-y-1">
                      {turn.retrieved_docs.map((doc, i) => (
                        <div key={i} className="bg-gray-800 rounded px-3 py-2 text-[11px] text-gray-400">
                          {doc.title && <span className="text-gray-300 font-medium">{doc.title} </span>}
                          {doc.score && <span className="text-green-500">({doc.score.toFixed(2)}) </span>}
                          {doc.text_snippet}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
