'use client';
import { useState, useEffect, useRef } from 'react';
import { HitlItem, ConversationTurn, approveHitl, fetchConversation, respondHitl, resolveHitl } from '@/lib/api';
import { CopyId } from '@/components/CopyId';

interface Props {
  items: HitlItem[];
  onResolved: () => void;
}

const RISK_COLORS: Record<string, string> = {
  low: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
  medium: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
  high: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
};

function LiveConversation({ sessionId }: { sessionId: string }) {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      fetchConversation(sessionId)
        .then((c) => { if (active) setTurns(c.turns ?? []); })
        .catch(() => {});
    load();
    const interval = setInterval(load, 3000);
    return () => { active = false; clearInterval(interval); };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  if (turns.length === 0) {
    return <p className="text-[11px] text-gray-400 dark:text-gray-500 italic">Loading conversation…</p>;
  }

  return (
    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
      {turns.map((t) => {
        const isHuman = t.route === 'human';
        const isUserHitl = t.route === 'hitl_pending' && !t.ai_response;
        const hasUserMsg = Boolean(t.user_query);
        const hasAiMsg = Boolean(t.ai_response);
        return (
          <div key={t.sk} className="space-y-1">
            {hasUserMsg && (
              <div className="flex justify-end">
                <div className="max-w-[80%] bg-gray-800 dark:bg-gray-700 text-white rounded-lg px-3 py-2 text-xs leading-relaxed">
                  {t.user_query}
                </div>
              </div>
            )}
            {hasAiMsg && !isUserHitl && (
              <div className="flex justify-start">
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-xs leading-relaxed border ${
                  isHuman
                    ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700 text-blue-900 dark:text-blue-100'
                    : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                }`}>
                  {isHuman && (
                    <p className="text-[9px] font-semibold text-blue-500 uppercase tracking-wider mb-1">Human Agent</p>
                  )}
                  {t.ai_response}
                </div>
              </div>
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}

function EscalationItem({ item, onResolved }: { item: HitlItem; onResolved: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [response, setResponse] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [resolving, setResolving] = useState(false);

  const handleSubmit = async () => {
    if (!response.trim()) return;
    setSubmitting(true);
    try {
      await respondHitl(item.sk, response);
      setResponse('');
      onResolved();
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    setResolving(true);
    try {
      await resolveHitl(item.sk);
      setExpanded(false);
      onResolved();
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="space-y-0.5 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded border bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800">
              ESCALATION
            </span>
            <CopyId id={item.session_id} />
          </div>
          <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400">
            <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-[10px] font-medium border border-gray-200 dark:border-gray-700">{item.trigger}</span>
            {item.rag_score && <span>RAG: <span className="font-mono text-gray-700 dark:text-gray-300">{parseFloat(item.rag_score).toFixed(2)}</span></span>}
            <span className="text-gray-400 dark:text-gray-500">{new Date(item.created_at).toLocaleString()}</span>
          </div>
        </div>
        <span className="text-gray-400 dark:text-gray-500 text-[10px] ml-4 flex-shrink-0">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <div className="bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 rounded-md p-3">
            <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Live Conversation</p>
            <LiveConversation sessionId={item.session_id} />
          </div>
          <textarea
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Type your response as the human agent…"
            className="input resize-none h-24 w-full"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={submitting || resolving || !response.trim()}
              className="btn-primary flex-1"
            >
              {submitting ? 'Sending…' : 'Send Response'}
            </button>
            <button
              onClick={handleResolve}
              disabled={submitting || resolving}
              className="px-4 py-2 rounded-md border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors"
            >
              {resolving ? 'Resolving…' : 'Resolve & Hand Back'}
            </button>
          </div>
          <p className="text-[10px] text-gray-400 dark:text-gray-500">
            Send Response to reply while keeping the session in queue. Resolve &amp; Hand Back returns control to the AI.
          </p>
        </div>
      )}
    </div>
  );
}

function ApprovalItem({ item, onResolved }: { item: HitlItem; onResolved: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null);

  const handleDecision = async (decision: 'approve' | 'reject') => {
    setSubmitting(decision);
    try {
      await approveHitl(item.sk, decision, note);
      setNote('');
      setExpanded(false);
      onResolved();
    } finally {
      setSubmitting(null);
    }
  };

  const riskClass = RISK_COLORS[item.risk_level ?? 'medium'];

  return (
    <div className="border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="space-y-0.5 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded border bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800">
              APPROVAL
            </span>
            <CopyId id={item.session_id} />
            {item.risk_level && (
              <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded border capitalize ${riskClass}`}>
                {item.risk_level} risk
              </span>
            )}
          </div>
          <p className="text-xs text-gray-700 dark:text-gray-300 truncate font-medium">
            {item.action_description ?? item.action_type ?? 'Unknown action'}
          </p>
          <span className="text-[11px] text-gray-400 dark:text-gray-500">{new Date(item.created_at).toLocaleString()}</span>
        </div>
        <span className="text-gray-400 dark:text-gray-500 text-[10px] ml-4 flex-shrink-0">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md p-3 space-y-2">
            <div className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">Action Requested</div>
            <p className="text-xs text-gray-700 dark:text-gray-300">{item.action_description}</p>
            {item.action_type && (
              <p className="text-[11px] text-gray-500 dark:text-gray-400 font-mono">type: {item.action_type}</p>
            )}
          </div>
          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md p-3 text-xs text-gray-600 dark:text-gray-400 leading-relaxed max-h-32 overflow-y-auto">
            <div className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1">Conversation Context</div>
            {item.conversation_summary || 'No context available.'}
          </div>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note to send back to the user…"
            className="input w-full"
          />
          <div className="flex gap-2">
            <button
              onClick={() => handleDecision('approve')}
              disabled={submitting !== null}
              className="flex-1 px-4 py-2 rounded-md bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-sm font-semibold transition-colors"
            >
              {submitting === 'approve' ? 'Approving…' : 'Approve'}
            </button>
            <button
              onClick={() => handleDecision('reject')}
              disabled={submitting !== null}
              className="flex-1 px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-sm font-semibold transition-colors"
            >
              {submitting === 'reject' ? 'Rejecting…' : 'Reject'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function HitlQueue({ items, onResolved }: Props) {
  if (items.length === 0) {
    return <p className="text-gray-400 dark:text-gray-500 text-sm p-5">No items in queue.</p>;
  }

  return (
    <div>
      {items.map((item) =>
        item.hitl_type === 'approval' ? (
          <ApprovalItem key={item.sk} item={item} onResolved={onResolved} />
        ) : (
          <EscalationItem key={item.sk} item={item} onResolved={onResolved} />
        )
      )}
    </div>
  );
}
