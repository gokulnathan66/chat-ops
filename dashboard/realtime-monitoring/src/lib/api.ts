const BASE = '/api';

export interface MetricsSummary {
  avg_rag_score: number;
  avg_faithfulness: number;
  cost_today_usd: number;
  hitl_pending: number;
  golden_pass_rate_pct: number;
}

export interface EvalRecord {
  session_id: string;
  sk: string;
  eval_type: string;
  rag_score?: string;
  faithfulness?: string;
  relevance?: string;
  re_retrieved?: string;
  hitl_flagged?: boolean;
  pca_topics?: string[];
  pca_sentiment?: string;
  pca_unresolved?: string[];
  created_at: string;
}

export interface GoldenResult {
  run_id: string;
  question_id: string;
  question: string;
  expected_answer: string;
  actual_answer: string;
  faithfulness: string;
  relevance: string;
  llm_judge_score: string;
  pass: boolean;
  run_at: string;
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

export async function fetchGoldenResults(runId?: string): Promise<GoldenResult[]> {
  const url = runId ? `${BASE}/golden-results?run_id=${runId}` : `${BASE}/golden-results`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch golden results');
  return res.json();
}
