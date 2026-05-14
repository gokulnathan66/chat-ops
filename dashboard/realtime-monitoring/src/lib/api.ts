const BASE = '/api';

export interface HitlItem {
  pk: string;
  sk: string;
  session_id: string;
  queue_status: string;
  trigger: string;
  hitl_type?: 'escalation' | 'approval';
  conversation_summary: string;
  rag_score: string;
  llm_judge_score: string;
  created_at: string;
  human_response?: string;
  resolved_at?: string;
  // approval-specific
  action_type?: string;
  action_description?: string;
  risk_level?: string;
  turn_n?: string;
}

export interface IngestionJob {
  session_id: string;
  sk: string;
  job_id?: string;
  eval_type: string;
  status: 'started' | 'running' | 'completed' | 'error';
  s3_key: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  chunks_indexed?: string;
  files_processed?: string;
  files_skipped?: string;
  files_errored?: string;
}

export interface StartIngestionResult {
  job_id: string;
  status: string;
  s3_key: string;
  filename?: string;
}

export interface MetricsSummary {
  avg_rag_score: number;
  avg_faithfulness: number;
  cost_today_usd: number;
  hitl_pending: number;
}

export interface EvalRecord {
  session_id: string;
  sk: string;
  eval_type: string;
  query?: string;
  rag_score?: string;
  faithfulness?: string;
  relevance?: string;
  re_retrieved?: string;
  hitl_flagged?: boolean;
  pca_topics?: string[];
  pca_sentiment?: string;
  pca_unresolved?: string[];
  // pca_alert fields
  negative_ratio?: string;
  avg_unresolved?: string;
  sessions_analyzed?: string;
  summary?: string;
  created_at: string;
}

export interface IngestedDoc {
  doc_id: string;
  title: string;
  source: string;
  url_or_file_path: string;
  tags: string[];
  created_at: string;
  chunk_count: number;
}

export interface GoldenQuery {
  session_id: string;
  sk: string;
  eval_type: string;
  query: string;
  created_at: string;
}

export interface ConversationTurn {
  sk: string;
  user_query: string;
  ai_response: string;
  route: string;
  intent: string;
  created_at: string;
}

export async function fetchConversation(sessionId: string): Promise<{ turns: ConversationTurn[] }> {
  const res = await fetch(`${BASE}/conversations/${encodeURIComponent(sessionId)}`);
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

export async function resolveHitl(queueId: string): Promise<void> {
  const res = await fetch(`${BASE}/hitl/${encodeURIComponent(queueId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to resolve HITL');
}

export async function approveHitl(queueId: string, decision: 'approve' | 'reject', note = ''): Promise<void> {
  const res = await fetch(`${BASE}/hitl/${encodeURIComponent(queueId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, note }),
  });
  if (!res.ok) throw new Error('Failed to submit approval decision');
}

export async function startIngestion(s3Key: string): Promise<StartIngestionResult> {
  const res = await fetch(`${BASE}/ingestion/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ s3_key: s3Key }),
  });
  if (!res.ok) throw new Error('Failed to start ingestion');
  return res.json();
}

export async function uploadAndIngest(file: File): Promise<StartIngestionResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/ingestion/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail ?? 'Upload failed');
  }
  return res.json();
}

export async function getIngestionStatus(jobId: string): Promise<IngestionJob> {
  const res = await fetch(`${BASE}/ingestion/status/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error('Failed to fetch job status');
  return res.json();
}

export async function getIngestionHistory(limit = 20): Promise<IngestionJob[]> {
  const res = await fetch(`${BASE}/ingestion/history?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch ingestion history');
  return res.json();
}

export async function fetchIngestedDocs(): Promise<IngestedDoc[]> {
  const res = await fetch(`${BASE}/ingestion/docs`);
  if (!res.ok) throw new Error('Failed to fetch ingested documents');
  return res.json();
}

export async function deleteIngestedDoc(docId: string): Promise<void> {
  const res = await fetch(`${BASE}/ingestion/docs/${encodeURIComponent(docId)}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete document');
}

export async function fetchMetrics(): Promise<MetricsSummary> {
  const res = await fetch(`${BASE}/metrics/summary`);
  if (!res.ok) throw new Error('Failed to fetch metrics');
  return res.json();
}

export async function fetchEvaluations(evalType = 'rag', limit = 50): Promise<EvalRecord[]> {
  const res = await fetch(`${BASE}/evaluations?type=${evalType}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch evaluations');
  return res.json();
}

export async function fetchGoldenQueries(): Promise<GoldenQuery[]> {
  const res = await fetch(`${BASE}/golden-queries`);
  if (!res.ok) throw new Error('Failed to fetch golden queries');
  return res.json();
}

export async function addGoldenQuery(query: string): Promise<GoldenQuery> {
  const res = await fetch(`${BASE}/golden-queries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error('Failed to add question');
  return res.json();
}

export async function updateGoldenQuery(queryId: string, query: string): Promise<void> {
  const res = await fetch(`${BASE}/golden-queries/${encodeURIComponent(queryId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error('Failed to update question');
}

export async function deleteGoldenQuery(queryId: string): Promise<void> {
  const res = await fetch(`${BASE}/golden-queries/${encodeURIComponent(queryId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete question');
}

