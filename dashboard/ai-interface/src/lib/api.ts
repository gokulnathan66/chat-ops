const BASE = '/api';

export interface RetrievedDoc {
  doc_id?: string;
  title?: string;
  score?: number;
  text_snippet?: string;
}

export interface Turn {
  sk: string;
  user_query: string;
  ai_response: string;
  intent: string;
  route: string;
  retrieved_docs: RetrievedDoc[];
  token_usage: { input: number; output: number };
  latency_ms: number;
  created_at: string;
}

export interface LocalTurn extends Turn {
  loading?: boolean;
  error?: boolean;
}

export type SessionStatus = 'active' | 'complete' | 'hitl_pending' | 'approval_pending';

export interface Session {
  session_id: string;
  status: SessionStatus;
  last_updated_at: string;
  turn_count: number;
}

export interface Conversation {
  metadata: Session;
  turns: Turn[];
}

export interface ChatResult {
  session_id?: string;
  message?: string;
  intent?: string;
  route?: string;
  retrieved_docs?: RetrievedDoc[];
  token_usage?: { input: number; output: number };
  latency_ms?: number;
}

export async function fetchSessions(status = 'active'): Promise<Session[]> {
  const res = await fetch(`${BASE}/conversations?status=${status}`);
  if (!res.ok) throw new Error('Failed to fetch sessions');
  return res.json();
}

export async function fetchConversation(sessionId: string): Promise<Conversation> {
  const res = await fetch(`${BASE}/conversations/${sessionId}`);
  if (!res.ok) throw new Error('Failed to fetch conversation');
  return res.json();
}

export async function fetchSessionMeta(sessionId: string): Promise<Session | null> {
  try {
    const conv = await fetchConversation(sessionId);
    return conv.metadata as Session;
  } catch {
    return null;
  }
}

export async function sendMessage(params: {
  user_query: string;
  session_id: string;
  turn: number;
}): Promise<ChatResult> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  const data: { result: ChatResult } = await res.json();
  return data.result;
}
