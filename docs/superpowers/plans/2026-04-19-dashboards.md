# Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Next.js dashboards: AI Interface (chat viewer, HITL queue, ingestion jobs) and Realtime Monitoring (KPI cards, RAG evals, golden dataset, PCA).

**Architecture:** Two independent Next.js 14 apps in `dashboard/ai-interface/` and `dashboard/realtime-monitoring/`. Both use the App Router and call the FastAPI backend (running at `NEXT_PUBLIC_API_URL`). No shared package — each app is self-contained. Shared UI patterns are duplicated (YAGNI).

**Tech Stack:** Next.js 14, React, TypeScript, Tailwind CSS, SWR (data fetching + polling)

**Prerequisite:** Backend Core plan must be complete (FastAPI running with dashboard endpoints).

---

## File Map — AI Interface (`dashboard/ai-interface/`)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `package.json` | Next.js 14 + Tailwind + SWR deps |
| Create | `next.config.js` | API proxy to FastAPI |
| Create | `tailwind.config.js` | Tailwind setup |
| Create | `src/app/layout.tsx` | Root layout, nav |
| Create | `src/app/page.tsx` | Session list + chat thread view |
| Create | `src/app/hitl/page.tsx` | HITL queue |
| Create | `src/app/ingestion/page.tsx` | Ingestion jobs |
| Create | `src/lib/api.ts` | Typed API client functions |
| Create | `src/components/SessionList.tsx` | Left sidebar session list |
| Create | `src/components/ChatThread.tsx` | Chat turn display |
| Create | `src/components/HitlQueue.tsx` | HITL queue table + respond modal |
| Create | `src/components/IngestionPanel.tsx` | Job table + start ingestion |

## File Map — Realtime Monitoring (`dashboard/realtime-monitoring/`)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `package.json` | Next.js 14 + Tailwind + SWR deps |
| Create | `next.config.js` | API proxy to FastAPI |
| Create | `tailwind.config.js` | Tailwind setup |
| Create | `src/app/layout.tsx` | Root layout, nav |
| Create | `src/app/page.tsx` | Overview: KPI cards + recent evals + PCA strip |
| Create | `src/app/evals/page.tsx` | Full RAG evaluations table |
| Create | `src/app/golden/page.tsx` | Golden dataset run history |
| Create | `src/app/pca/page.tsx` | PCA results |
| Create | `src/lib/api.ts` | Typed API client |
| Create | `src/components/KpiCards.tsx` | 5 KPI summary cards |
| Create | `src/components/EvalTable.tsx` | RAG eval table with score coloring |
| Create | `src/components/GoldenTable.tsx` | Golden result table with pass/fail badges |
| Create | `src/components/PcaPanel.tsx` | Topics, sentiment, unresolved list |

---

## Task 1: AI Interface — project setup

**Files:**
- Create: `dashboard/ai-interface/package.json`
- Create: `dashboard/ai-interface/next.config.js`
- Create: `dashboard/ai-interface/tailwind.config.js`
- Create: `dashboard/ai-interface/tsconfig.json`
- Create: `dashboard/ai-interface/postcss.config.js`
- Create: `dashboard/ai-interface/src/app/globals.css`

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd dashboard/ai-interface
npx create-next-app@14 . --typescript --tailwind --app --src-dir --no-eslint --import-alias "@/*"
```

When prompted, accept all defaults.

- [ ] **Step 2: Install SWR**

```bash
npm install swr
```

- [ ] **Step 3: Configure API proxy in `next.config.js`**

Replace the contents of `dashboard/ai-interface/next.config.js`:

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 4: Create `.env.local`**

```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

- [ ] **Step 5: Verify dev server starts**

```bash
npm run dev &
sleep 3
curl -s http://localhost:3000
kill %1
```

Expected: HTML response (Next.js default page).

- [ ] **Step 6: Commit**

```bash
cd ../..
git add dashboard/ai-interface/
git commit -m "feat: scaffold AI Interface Next.js app"
```

---

## Task 2: AI Interface — API client

**Files:**
- Create: `dashboard/ai-interface/src/lib/api.ts`

- [ ] **Step 1: Create `dashboard/ai-interface/src/lib/api.ts`**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ai-interface/src/lib/api.ts
git commit -m "feat: add AI Interface typed API client"
```

---

## Task 3: AI Interface — root layout + nav

**Files:**
- Modify: `dashboard/ai-interface/src/app/layout.tsx`
- Modify: `dashboard/ai-interface/src/app/globals.css`

- [ ] **Step 1: Update `dashboard/ai-interface/src/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'LLMOps — AI Interface',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
          <span className="font-bold text-white">LLMOps</span>
          <Link href="/" className="text-gray-400 hover:text-white transition-colors">Chat</Link>
          <Link href="/hitl" className="text-gray-400 hover:text-white transition-colors">HITL Queue</Link>
          <Link href="/ingestion" className="text-gray-400 hover:text-white transition-colors">Ingestion</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ai-interface/src/app/layout.tsx
git commit -m "feat: add AI Interface nav layout"
```

---

## Task 4: AI Interface — SessionList + ChatThread components

**Files:**
- Create: `dashboard/ai-interface/src/components/SessionList.tsx`
- Create: `dashboard/ai-interface/src/components/ChatThread.tsx`
- Modify: `dashboard/ai-interface/src/app/page.tsx`

- [ ] **Step 1: Create `dashboard/ai-interface/src/components/SessionList.tsx`**

```tsx
'use client';
import { Session } from '@/lib/api';

interface Props {
  sessions: Session[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function SessionList({ sessions, selectedId, onSelect }: Props) {
  return (
    <div className="w-56 border-r border-gray-800 h-full overflow-y-auto p-3 flex-shrink-0">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-3">Sessions</p>
      {sessions.length === 0 && (
        <p className="text-xs text-gray-600">No sessions found.</p>
      )}
      {sessions.map((s) => (
        <button
          key={s.session_id}
          onClick={() => onSelect(s.session_id)}
          className={`w-full text-left px-3 py-2 rounded text-xs mb-1 transition-colors truncate ${
            selectedId === s.session_id
              ? 'bg-blue-900 text-blue-200'
              : 'text-gray-400 hover:bg-gray-800'
          }`}
        >
          {s.session_id.slice(0, 20)}…
          <span className="block text-gray-600 text-[10px]">{s.turn_count} turns</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/ai-interface/src/components/ChatThread.tsx`**

```tsx
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
```

- [ ] **Step 3: Update `dashboard/ai-interface/src/app/page.tsx`**

```tsx
'use client';
import { useState } from 'react';
import useSWR from 'swr';
import SessionList from '@/components/SessionList';
import ChatThread from '@/components/ChatThread';
import { fetchSessions, fetchConversation, respondHitl, Session, Conversation } from '@/lib/api';

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
```

- [ ] **Step 4: Verify dev server compiles without errors**

```bash
cd dashboard/ai-interface && npm run dev &
sleep 5
curl -s http://localhost:3000 | grep -q "LLMOps" && echo "OK"
kill %1
cd ../..
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add dashboard/ai-interface/src/
git commit -m "feat: add AI Interface SessionList, ChatThread, and home page"
```

---

## Task 5: AI Interface — HITL queue page

**Files:**
- Create: `dashboard/ai-interface/src/components/HitlQueue.tsx`
- Create: `dashboard/ai-interface/src/app/hitl/page.tsx`

- [ ] **Step 1: Create `dashboard/ai-interface/src/components/HitlQueue.tsx`**

```tsx
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
```

- [ ] **Step 2: Create `dashboard/ai-interface/src/app/hitl/page.tsx`**

```tsx
'use client';
import useSWR from 'swr';
import HitlQueue from '@/components/HitlQueue';
import { HitlItem } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function HitlPage() {
  const { data: pending = [], mutate: mutatePending } = useSWR<HitlItem[]>(
    '/api/hitl?status=pending', fetcher, { refreshInterval: 15000 }
  );
  const { data: resolved = [] } = useSWR<HitlItem[]>(
    '/api/hitl?status=resolved', fetcher, { refreshInterval: 30000 }
  );

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div>
        <h2 className="text-lg font-semibold mb-1">Pending</h2>
        <p className="text-xs text-gray-500 mb-4">Sessions flagged by evaluators or escalated by users.</p>
        <div className="border border-gray-800 rounded-lg">
          <HitlQueue items={pending} onResolved={() => mutatePending()} />
        </div>
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-1 text-gray-500">Resolved</h2>
        <div className="border border-gray-800 rounded-lg divide-y divide-gray-800">
          {resolved.length === 0 && <p className="text-gray-600 text-sm p-4">None resolved yet.</p>}
          {resolved.map((item) => (
            <div key={item.sk} className="p-4 text-xs text-gray-500">
              <span className="font-mono text-gray-400">{item.session_id.slice(0, 24)}…</span>
              <span className="ml-3">{item.human_response?.slice(0, 80)}…</span>
              <span className="ml-3 text-gray-600">{item.resolved_at ? new Date(item.resolved_at).toLocaleString() : ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/ai-interface/src/components/HitlQueue.tsx dashboard/ai-interface/src/app/hitl/
git commit -m "feat: add HITL queue page with respond modal"
```

---

## Task 6: AI Interface — Ingestion page

**Files:**
- Create: `dashboard/ai-interface/src/components/IngestionPanel.tsx`
- Create: `dashboard/ai-interface/src/app/ingestion/page.tsx`

- [ ] **Step 1: Create `dashboard/ai-interface/src/components/IngestionPanel.tsx`**

```tsx
'use client';
import { useState } from 'react';
import { startIngestion } from '@/lib/api';

export default function IngestionPanel() {
  const [s3Key, setS3Key] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!s3Key.trim()) return;
    setSubmitting(true);
    setMessage(null);
    try {
      await startIngestion(s3Key.trim());
      setMessage(`Ingestion started for: ${s3Key}`);
      setS3Key('');
    } catch {
      setMessage('Failed to start ingestion. Check S3 key and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border border-gray-800 rounded-lg p-5 max-w-lg">
      <h3 className="text-sm font-semibold mb-3">Start New Ingestion Job</h3>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={s3Key}
          onChange={(e) => setS3Key(e.target.value)}
          placeholder="documents/my-file.pdf"
          className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
        />
        <button
          type="submit"
          disabled={submitting || !s3Key.trim()}
          className="px-4 py-2 text-xs bg-green-800 hover:bg-green-700 disabled:opacity-50 rounded text-white transition-colors whitespace-nowrap"
        >
          {submitting ? 'Starting…' : '+ Start Ingestion'}
        </button>
      </form>
      {message && (
        <p className={`mt-2 text-xs ${message.startsWith('Failed') ? 'text-red-400' : 'text-green-400'}`}>
          {message}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/ai-interface/src/app/ingestion/page.tsx`**

```tsx
import IngestionPanel from '@/components/IngestionPanel';

export default function IngestionPage() {
  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Document Ingestion</h2>
        <p className="text-xs text-gray-500 mb-4">
          Trigger ingestion of a document from S3 into the Qdrant vector store.
          Provide the S3 object key (not the full URL).
        </p>
        <IngestionPanel />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Final build check for AI Interface**

```bash
cd dashboard/ai-interface && npm run build 2>&1 | tail -5
cd ../..
```

Expected: `✓ Compiled successfully` or similar success message.

- [ ] **Step 4: Commit**

```bash
git add dashboard/ai-interface/src/components/IngestionPanel.tsx dashboard/ai-interface/src/app/ingestion/
git commit -m "feat: add ingestion trigger page"
```

---

## Task 7: Realtime Monitoring — project setup + API client

**Files:**
- Create: `dashboard/realtime-monitoring/` (full Next.js scaffold)
- Create: `dashboard/realtime-monitoring/src/lib/api.ts`

- [ ] **Step 1: Scaffold**

```bash
cd dashboard/realtime-monitoring
npx create-next-app@14 . --typescript --tailwind --app --src-dir --no-eslint --import-alias "@/*"
npm install swr
```

- [ ] **Step 2: Configure proxy in `dashboard/realtime-monitoring/next.config.js`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 3: Create `.env.local`**

```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

- [ ] **Step 4: Create `dashboard/realtime-monitoring/src/lib/api.ts`**

```typescript
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
  const res = await fetch(`${BASE}/evaluations?eval_type=${evalType}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch evaluations');
  return res.json();
}

export async function fetchGoldenResults(runId?: string): Promise<GoldenResult[]> {
  const url = runId ? `${BASE}/golden-results?run_id=${runId}` : `${BASE}/golden-results`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch golden results');
  return res.json();
}
```

- [ ] **Step 5: Commit**

```bash
cd ../..
git add dashboard/realtime-monitoring/
git commit -m "feat: scaffold Realtime Monitoring Next.js app"
```

---

## Task 8: Realtime Monitoring — KpiCards + layout + overview page

**Files:**
- Modify: `dashboard/realtime-monitoring/src/app/layout.tsx`
- Create: `dashboard/realtime-monitoring/src/components/KpiCards.tsx`
- Modify: `dashboard/realtime-monitoring/src/app/page.tsx`

- [ ] **Step 1: Update `dashboard/realtime-monitoring/src/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = { title: 'LLMOps — Monitoring' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
          <span className="font-bold text-white">LLMOps Monitor</span>
          <Link href="/" className="text-gray-400 hover:text-white transition-colors">Overview</Link>
          <Link href="/evals" className="text-gray-400 hover:text-white transition-colors">RAG Evals</Link>
          <Link href="/golden" className="text-gray-400 hover:text-white transition-colors">Golden Dataset</Link>
          <Link href="/pca" className="text-gray-400 hover:text-white transition-colors">PCA</Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create `dashboard/realtime-monitoring/src/components/KpiCards.tsx`**

```tsx
import { MetricsSummary } from '@/lib/api';

function KpiCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

export default function KpiCards({ metrics }: { metrics: MetricsSummary }) {
  return (
    <div className="grid grid-cols-5 gap-4">
      <KpiCard label="Golden Pass Rate" value={`${metrics.golden_pass_rate_pct}%`} color="text-green-400" />
      <KpiCard label="Avg RAG Score" value={metrics.avg_rag_score.toFixed(2)} color="text-blue-400" />
      <KpiCard label="Avg Faithfulness" value={metrics.avg_faithfulness.toFixed(2)} color="text-purple-400" />
      <KpiCard label="Cost Today" value={`$${metrics.cost_today_usd.toFixed(4)}`} color="text-yellow-400" />
      <KpiCard label="HITL Pending" value={String(metrics.hitl_pending)} color={metrics.hitl_pending > 0 ? 'text-red-400' : 'text-gray-400'} />
    </div>
  );
}
```

- [ ] **Step 3: Update `dashboard/realtime-monitoring/src/app/page.tsx`**

```tsx
'use client';
import useSWR from 'swr';
import KpiCards from '@/components/KpiCards';
import { MetricsSummary, EvalRecord, fetchMetrics, fetchEvaluations } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function scoreColor(score: string | undefined) {
  if (!score) return 'text-gray-500';
  const n = parseFloat(score);
  if (n >= 0.8) return 'text-green-400';
  if (n >= 0.6) return 'text-yellow-400';
  return 'text-red-400';
}

export default function OverviewPage() {
  const { data: metrics } = useSWR<MetricsSummary>('/api/metrics/summary', fetcher, { refreshInterval: 30000 });
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?eval_type=rag&limit=10', fetcher, { refreshInterval: 30000 });
  const { data: pcaEvals = [] } = useSWR<EvalRecord[]>('/api/evaluations?eval_type=pca&limit=1', fetcher, { refreshInterval: 30000 });

  const latestPca = pcaEvals[0];

  return (
    <div className="space-y-8 max-w-6xl">
      {metrics ? <KpiCards metrics={metrics} /> : (
        <div className="grid grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-20 animate-pulse" />
          ))}
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Recent RAG Evaluations</h2>
        <div className="border border-gray-800 rounded-lg overflow-hidden">
          <div className="grid grid-cols-5 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900">
            <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Re-retrieved</span><span>HITL</span>
          </div>
          {evals.length === 0 && <p className="text-gray-600 text-sm p-4">No evaluations yet.</p>}
          {evals.map((e) => (
            <div key={e.sk} className="grid grid-cols-5 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900">
              <span className="font-mono text-blue-400 truncate">{e.session_id.slice(0, 18)}…</span>
              <span className={scoreColor(e.rag_score)}>{e.rag_score ? parseFloat(e.rag_score).toFixed(2) : '—'}</span>
              <span className={scoreColor(e.faithfulness)}>{e.faithfulness ? parseFloat(e.faithfulness).toFixed(2) : '—'}</span>
              <span className={e.re_retrieved === 'True' ? 'text-yellow-400' : 'text-gray-500'}>{e.re_retrieved === 'True' ? 'Yes' : 'No'}</span>
              <span className={e.hitl_flagged ? 'text-red-400 font-semibold' : 'text-gray-600'}>{e.hitl_flagged ? '⚑ Flagged' : '—'}</span>
            </div>
          ))}
        </div>
      </div>

      {latestPca && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-3">Latest PCA</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            {latestPca.pca_topics?.map((t) => (
              <span key={t} className="bg-purple-900 text-purple-300 px-3 py-1 rounded-full">{t}</span>
            ))}
            <span className={`px-3 py-1 rounded-full font-medium ${
              latestPca.pca_sentiment === 'positive' ? 'bg-green-900 text-green-300' :
              latestPca.pca_sentiment === 'negative' ? 'bg-red-900 text-red-300' :
              'bg-gray-800 text-gray-400'
            }`}>
              {latestPca.pca_sentiment}
            </span>
            {latestPca.pca_unresolved?.map((q) => (
              <span key={q} className="bg-red-950 text-red-400 px-3 py-1 rounded-full">❓ {q}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/realtime-monitoring/src/
git commit -m "feat: add Monitoring overview page with KPI cards, eval table, PCA strip"
```

---

## Task 9: Realtime Monitoring — Evals, Golden, PCA pages

**Files:**
- Create: `dashboard/realtime-monitoring/src/app/evals/page.tsx`
- Create: `dashboard/realtime-monitoring/src/app/golden/page.tsx`
- Create: `dashboard/realtime-monitoring/src/app/pca/page.tsx`

- [ ] **Step 1: Create `dashboard/realtime-monitoring/src/app/evals/page.tsx`**

```tsx
'use client';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function score(val: string | undefined) {
  if (!val) return <span className="text-gray-600">—</span>;
  const n = parseFloat(val);
  const cls = n >= 0.8 ? 'text-green-400' : n >= 0.6 ? 'text-yellow-400' : 'text-red-400';
  return <span className={cls}>{n.toFixed(3)}</span>;
}

export default function EvalsPage() {
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?eval_type=rag&limit=100', fetcher, { refreshInterval: 30000 });

  return (
    <div className="max-w-6xl space-y-4">
      <h2 className="text-lg font-semibold">RAG Evaluations</h2>
      <div className="border border-gray-800 rounded-lg overflow-auto">
        <div className="grid grid-cols-6 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900 min-w-[700px]">
          <span>Session</span><span>RAG Score</span><span>Faithfulness</span><span>Relevance</span><span>Re-retrieved</span><span>HITL</span>
        </div>
        {evals.length === 0 && <p className="text-gray-600 text-sm p-4">No evaluations yet.</p>}
        {evals.map((e) => (
          <div key={e.sk} className="grid grid-cols-6 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900 min-w-[700px]">
            <span className="font-mono text-blue-400 truncate">{e.session_id.slice(0, 16)}…</span>
            {score(e.rag_score)}
            {score(e.faithfulness)}
            {score(e.relevance)}
            <span className={e.re_retrieved === 'True' ? 'text-yellow-400' : 'text-gray-600'}>
              {e.re_retrieved === 'True' ? 'Yes' : 'No'}
            </span>
            <span className={e.hitl_flagged ? 'text-red-400 font-semibold' : 'text-gray-600'}>
              {e.hitl_flagged ? '⚑' : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/realtime-monitoring/src/app/golden/page.tsx`**

```tsx
'use client';
import useSWR from 'swr';
import { GoldenResult } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function GoldenPage() {
  const { data: results = [] } = useSWR<GoldenResult[]>('/api/golden-results', fetcher, { refreshInterval: 60000 });

  const runs = Array.from(new Set(results.map((r) => r.run_id)));
  const passRate = results.length > 0
    ? Math.round((results.filter((r) => r.pass).length / results.length) * 100)
    : 0;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-6">
        <h2 className="text-lg font-semibold">Golden Dataset</h2>
        <span className="text-sm text-gray-500">{runs.length} run(s) · Overall pass rate:
          <span className={`ml-1 font-bold ${passRate >= 80 ? 'text-green-400' : passRate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
            {passRate}%
          </span>
        </span>
      </div>

      <div className="border border-gray-800 rounded-lg overflow-auto">
        <div className="grid grid-cols-5 px-4 py-2 text-[11px] text-gray-600 border-b border-gray-800 bg-gray-900 min-w-[700px]">
          <span className="col-span-2">Question</span><span>Judge Score</span><span>Run</span><span>Pass</span>
        </div>
        {results.length === 0 && <p className="text-gray-600 text-sm p-4">No golden results yet.</p>}
        {results.map((r) => (
          <div key={`${r.run_id}-${r.question_id}`} className="grid grid-cols-5 px-4 py-2.5 text-xs border-b border-gray-900 hover:bg-gray-900 min-w-[700px]">
            <span className="col-span-2 text-gray-300 truncate">{r.question}</span>
            <span className={parseFloat(r.llm_judge_score) >= 0.7 ? 'text-green-400' : 'text-red-400'}>
              {parseFloat(r.llm_judge_score).toFixed(2)}
            </span>
            <span className="font-mono text-gray-500 text-[10px]">{r.run_id.slice(0, 12)}…</span>
            <span className={r.pass ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
              {r.pass ? '✓ Pass' : '✗ Fail'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `dashboard/realtime-monitoring/src/app/pca/page.tsx`**

```tsx
'use client';
import useSWR from 'swr';
import { EvalRecord } from '@/lib/api';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function PcaPage() {
  const { data: pcaEvals = [] } = useSWR<EvalRecord[]>('/api/evaluations?eval_type=pca&limit=50', fetcher, { refreshInterval: 30000 });

  const allTopics = pcaEvals.flatMap((e) => e.pca_topics ?? []);
  const topicCounts = allTopics.reduce<Record<string, number>>((acc, t) => {
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {});
  const topTopics = Object.entries(topicCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const sentimentCounts = { positive: 0, neutral: 0, negative: 0 };
  for (const e of pcaEvals) {
    const s = e.pca_sentiment as keyof typeof sentimentCounts;
    if (s in sentimentCounts) sentimentCounts[s]++;
  }

  const allUnresolved = pcaEvals.flatMap((e) => e.pca_unresolved ?? []);

  return (
    <div className="max-w-4xl space-y-8">
      <h2 className="text-lg font-semibold">Post-Conversation Analysis</h2>

      <div className="grid grid-cols-2 gap-6">
        <div className="border border-gray-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-400">Top Topics</h3>
          {topTopics.length === 0 && <p className="text-xs text-gray-600">No data yet.</p>}
          {topTopics.map(([topic, count]) => (
            <div key={topic} className="flex items-center gap-3">
              <div className="flex-1 text-xs text-gray-300 truncate">{topic}</div>
              <div className="w-24 bg-gray-800 rounded-full h-1.5">
                <div
                  className="bg-purple-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, (count / pcaEvals.length) * 100)}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 w-6 text-right">{count}</div>
            </div>
          ))}
        </div>

        <div className="border border-gray-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-400">Sentiment Distribution</h3>
          {(['positive', 'neutral', 'negative'] as const).map((s) => (
            <div key={s} className="flex items-center gap-3">
              <div className="w-16 text-xs text-gray-400 capitalize">{s}</div>
              <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${s === 'positive' ? 'bg-green-500' : s === 'negative' ? 'bg-red-500' : 'bg-gray-500'}`}
                  style={{ width: pcaEvals.length ? `${(sentimentCounts[s] / pcaEvals.length) * 100}%` : '0%' }}
                />
              </div>
              <div className="text-xs text-gray-500 w-6 text-right">{sentimentCounts[s]}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-3">Unresolved Questions</h3>
        {allUnresolved.length === 0 && <p className="text-xs text-gray-600">None recorded yet.</p>}
        <ul className="space-y-1">
          {allUnresolved.map((q, i) => (
            <li key={i} className="text-xs text-red-300 flex items-start gap-2">
              <span className="text-red-600 mt-0.5">❓</span>{q}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Final build check for Realtime Monitoring**

```bash
cd dashboard/realtime-monitoring && npm run build 2>&1 | tail -5
cd ../..
```

Expected: `✓ Compiled successfully`

- [ ] **Step 5: Final commit**

```bash
git add dashboard/realtime-monitoring/src/app/evals/ dashboard/realtime-monitoring/src/app/golden/ dashboard/realtime-monitoring/src/app/pca/
git commit -m "feat: dashboards complete - evals, golden dataset, and PCA pages"
```

---

## Task 10: Add .superpowers to .gitignore

- [ ] **Step 1: Add .superpowers/ to .gitignore**

```bash
echo ".superpowers/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore .superpowers brainstorm files"
```
