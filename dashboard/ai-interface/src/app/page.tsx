'use client';
import { useCallback, useEffect, useState } from 'react';
import useSWR from 'swr';
import SessionList from '@/components/SessionList';
import ChatThread from '@/components/ChatThread';
import { LocalTurn, Session, SessionStatus, fetchConversation, sendMessage } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function HomePage() {
  const { data: sessions = [], mutate: mutateSessions } = useSWR<Session[]>(
    '/api/conversations?status=all',
    fetcher,
    { refreshInterval: 15000 },
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('active');
  const [turns, setTurns] = useState<LocalTurn[]>([]);
  const [turnCount, setTurnCount] = useState(0);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const isPending = sessionStatus === 'hitl_pending' || sessionStatus === 'approval_pending';

  // Poll session status + turns every 5s while waiting for human/approval response
  useSWR(
    selectedId && isPending ? `/api/conversations/${selectedId}` : null,
    (url) => fetch(url).then((r) => r.json()),
    {
      refreshInterval: 5000,
      onSuccess: (data) => {
        const meta: Session = data.metadata;
        if (!meta) return;
        setSessionStatus((meta.status as SessionStatus) ?? 'active');
        const serverTurns: LocalTurn[] = (data.turns ?? []) as LocalTurn[];
        // Reload turns whenever server has more (catches human and user replies during hitl_pending)
        if (serverTurns.length > turnCount || meta.status === 'active' || meta.status === 'hitl_pending') {
          setTurns(serverTurns);
          setTurnCount(serverTurns.length);
        }
      },
    }
  );

  // Load conversation history when session changes
  useEffect(() => {
    if (!selectedId) {
      setTurns([]);
      setTurnCount(0);
      return;
    }
    setLoadingHistory(true);
    fetchConversation(selectedId)
      .then((conv) => {
        setTurns(conv.turns as LocalTurn[]);
        setTurnCount(conv.turns.length);
        setSessionStatus((conv.metadata?.status as SessionStatus) ?? 'active');
      })
      .catch(() => {
        setTurns([]);
        setTurnCount(0);
        setSessionStatus('active');
      })
      .finally(() => setLoadingHistory(false));
  }, [selectedId]);

  const handleNewChat = useCallback(() => {
    const id = crypto.randomUUID();
    const newSession: Session = {
      session_id: id,
      status: 'active',
      last_updated_at: new Date().toISOString(),
      turn_count: 0,
    };
    mutateSessions([newSession, ...sessions], false);
    setSelectedId(id);
    setSessionStatus('active');
    setTurns([]);
    setTurnCount(0);
  }, [sessions, mutateSessions]);

  const handleSelectSession = useCallback((id: string) => {
    if (id === selectedId) return;
    setSelectedId(id);
    setSessionStatus('active');
  }, [selectedId]);

  const handleSend = useCallback(async (query: string) => {
    if (!selectedId || !query.trim() || sending) return;

    const nextTurn = turnCount + 1;
    const tempSk = `turn#${String(nextTurn).padStart(3, '0')}`;

    const isHitlSession = sessionStatus === 'hitl_pending';
    const optimisticTurn: LocalTurn = {
      sk: tempSk,
      user_query: query.trim(),
      ai_response: '',
      intent: isHitlSession ? 'hitl_user_reply' : '',
      route: isHitlSession ? 'hitl_pending' : '',
      retrieved_docs: [],
      token_usage: { input: 0, output: 0 },
      latency_ms: 0,
      created_at: new Date().toISOString(),
      loading: !isHitlSession,  // no typing indicator for hitl user replies
    };

    setTurns((prev) => [...prev, optimisticTurn]);
    setTurnCount(nextTurn);
    setSending(true);

    try {
      const result = await sendMessage({
        user_query: query.trim(),
        session_id: selectedId,
        turn: nextTurn,
      });

      const route = result.route ?? '';
      setTurns((prev) =>
        prev.map((t) =>
          t.sk === tempSk
            ? {
                ...t,
                ai_response: result.message ?? '',
                intent: result.intent ?? '',
                route,
                retrieved_docs: result.retrieved_docs ?? [],
                token_usage: result.token_usage ?? { input: 0, output: 0 },
                latency_ms: result.latency_ms ?? 0,
                loading: false,
              }
            : t,
        ),
      );

      if (route === 'escalate') setSessionStatus('hitl_pending');
      else if (route === 'approval_required') setSessionStatus('approval_pending');
      // hitl_pending route means user replied during HITL — status stays hitl_pending, no change needed

      mutateSessions();
    } catch {
      setTurns((prev) =>
        prev.map((t) =>
          t.sk === tempSk
            ? { ...t, ai_response: 'Request failed. Please try again.', loading: false, error: true }
            : t,
        ),
      );
    } finally {
      setSending(false);
    }
  }, [selectedId, turnCount, sending, mutateSessions]);

  const handleEscalate = useCallback(async () => {
    if (!selectedId || isPending) return;
    await fetch('/api/hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: selectedId, trigger: 'user_escalation' }),
    });
    setSessionStatus('hitl_pending');
  }, [selectedId, isPending]);

  return (
    <div className="flex h-full">
      <SessionList
        sessions={sessions}
        selectedId={selectedId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
      />
      {selectedId ? (
        <ChatThread
          sessionId={selectedId}
          sessionStatus={sessionStatus}
          turns={turns}
          sending={sending}
          loadingHistory={loadingHistory}
          onSend={handleSend}
          onEscalate={handleEscalate}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-950">
          <div className="text-center space-y-3">
            <p className="text-2xl">💬</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Select a session or start a new chat</p>
            <button onClick={handleNewChat} className="btn-primary">
              New Chat
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
