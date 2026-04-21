'use client';
import { useState } from 'react';
import useSWR from 'swr';
import SessionList from '@/components/SessionList';
import ChatThread from '@/components/ChatThread';
import { Session, Conversation } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function HomePage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: sessions = [] } = useSWR<Session[]>('/api/conversations?status=active', fetcher, { refreshInterval: 10000 });
  const { data: conversation } = useSWR<Conversation>(
    selectedId ? `/api/conversations/${selectedId}` : null,
    fetcher
  );

  const handleEscalate = async () => {
    if (!selectedId) return;
    await fetch('/api/hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: selectedId, trigger: 'user_escalation' }),
    });
    alert('Session escalated to human queue.');
  };

  return (
    <div className="flex h-[calc(100vh-49px)]">
      <SessionList sessions={sessions} selectedId={selectedId} onSelect={setSelectedId} />
      {conversation ? (
        <ChatThread conversation={conversation} onEscalate={handleEscalate} />
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          Select a session to view the chat thread.
        </div>
      )}
    </div>
  );
}
