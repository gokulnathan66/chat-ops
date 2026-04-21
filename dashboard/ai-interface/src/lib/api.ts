const BASE = '/api';

export interface Turn {
  sk: string;
  user_query: string;
  ai_response: string;
  intent: string;
  route: string;
  retrieved_docs: { doc_id?: string; title?: string; score?: number; text_snippet?: string }[];
  token_usage: { input: number; output: number };
  latency_ms: number;
  created_at: string;
}

export interface Session {
  session_id: string;
  status: string;
  last_updated_at: string;
  turn_count: number;
}

export interface Conversation {
  metadata: Session;
  turns: Turn[];
}

export interface HitlItem {
  pk: string;
  sk: string;
  session_id: string;
  queue_status: string;
  trigger: string;
  conversation_summary: string;
  rag_score: string;
  llm_judge_score: string;
  created_at: string;
  human_response?: string;
  resolved_at?: string;
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

export async function fetchHitlQueue(status = 'pending'): Promise<HitlItem[]> {
  const res = await fetch(`${BASE}/hitl?status=${status}`);
  if (!res.ok) throw new Error('Failed to fetch HITL queue');
  return res.json();
}

export async function respondHitl(queueId: string, humanResponse: string): Promise<void> {
  const res = await fetch(`${BASE}/hitl/${encodeURIComponent(queueId)}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_response: humanResponse }),
  });
  if (!res.ok) throw new Error('Failed to submit HITL response');
}

export async function startIngestion(s3Key: string): Promise<void> {
  const res = await fetch(`${BASE}/ingestion/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ s3_key: s3Key }),
  });
  if (!res.ok) throw new Error('Failed to start ingestion');
}
