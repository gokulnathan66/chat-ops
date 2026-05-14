'use client';
import { useState, useRef } from 'react';
import useSWR from 'swr';
import { EvalRecord, GoldenQuery, addGoldenQuery, updateGoldenQuery, deleteGoldenQuery } from '@/lib/api';
import { ScoreBar } from '@/components/ScoreBar';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface QuestionRowProps {
  question: GoldenQuery;
  onSave: (id: string, text: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

function QuestionRow({ question, onSave, onDelete }: QuestionRowProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(question.query);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!draft.trim() || draft === question.query) { setEditing(false); return; }
    setSaving(true);
    await onSave(question.session_id, draft.trim());
    setSaving(false);
    setEditing(false);
  }

  return (
    <div className="flex items-start gap-2 py-2 px-3 group hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg">
      <span className="text-gray-300 dark:text-gray-600 text-xs font-mono mt-0.5 flex-shrink-0">›</span>
      {editing ? (
        <div className="flex-1 flex items-center gap-2">
          <input
            autoFocus
            className="flex-1 text-xs bg-white dark:bg-gray-800 border border-brand-400 rounded px-2 py-1 outline-none text-gray-900 dark:text-gray-100"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false); }}
          />
          <button onClick={handleSave} disabled={saving} className="text-xs text-brand-600 dark:text-brand-400 font-medium disabled:opacity-50">
            {saving ? '…' : 'Save'}
          </button>
          <button onClick={() => setEditing(false)} className="text-xs text-gray-400">Cancel</button>
        </div>
      ) : (
        <>
          <span className="flex-1 text-xs text-gray-700 dark:text-gray-300 leading-relaxed">{question.query}</span>
          <div className="hidden group-hover:flex items-center gap-1.5 flex-shrink-0">
            <button onClick={() => { setDraft(question.query); setEditing(true); }} className="text-[10px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">Edit</button>
            <button onClick={() => onDelete(question.session_id)} className="text-[10px] text-red-400 hover:text-red-600">Delete</button>
          </div>
        </>
      )}
    </div>
  );
}

export default function EvalsPage() {
  const { data: questions = [], mutate: mutateQuestions } = useSWR<GoldenQuery[]>('/api/golden-queries', fetcher, { refreshInterval: 60000 });
  const { data: evals = [] } = useSWR<EvalRecord[]>('/api/evaluations?type=rag&limit=200', fetcher, { refreshInterval: 15000 });

  const [newQuestion, setNewQuestion] = useState('');
  const [adding, setAdding] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Group evals by query, keep only latest per query
  const latestByQuery = Object.values(
    evals.reduce<Record<string, EvalRecord>>((acc, e) => {
      const q = e.query ?? '';
      if (!q) return acc;
      if (!acc[q] || e.created_at > acc[q].created_at) acc[q] = e;
      return acc;
    }, {})
  );

  async function handleAdd() {
    const q = newQuestion.trim();
    if (!q) return;
    setAdding(true);
    try {
      const created = await addGoldenQuery(q);
      mutateQuestions([...questions, created as GoldenQuery]);
      setNewQuestion('');
    } finally {
      setAdding(false);
    }
  }

  async function handleSave(id: string, text: string) {
    await updateGoldenQuery(id, text);
    mutateQuestions(questions.map((q) => q.session_id === id ? { ...q, query: text } : q));
  }

  async function handleDelete(id: string) {
    await deleteGoldenQuery(id);
    mutateQuestions(questions.filter((q) => q.session_id !== id));
  }

  const avgRag = latestByQuery.length
    ? latestByQuery.reduce((s, e) => s + parseFloat(e.rag_score ?? '0'), 0) / latestByQuery.length
    : null;

  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">Evaluation</p>
        <h1 className="page-title">RAG Evaluations</h1>
        <p className="page-subtitle">Define test questions and monitor retrieval quality after every document ingest.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Questions panel */}
        <div className="card p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Questions</h3>
            <span className="text-xs text-gray-400 font-mono">{questions.length}</span>
          </div>

          <div className="flex-1 space-y-0.5 max-h-96 overflow-y-auto">
            {questions.length === 0 && (
              <p className="text-xs text-gray-400 dark:text-gray-500 px-3 py-2">No questions yet. Add one below.</p>
            )}
            {questions.map((q) => (
              <QuestionRow key={q.session_id} question={q} onSave={handleSave} onDelete={handleDelete} />
            ))}
          </div>

          <div className="flex gap-2 pt-1 border-t border-gray-100 dark:border-gray-700">
            <input
              ref={inputRef}
              className="flex-1 text-xs bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5 outline-none focus:border-brand-400 text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
              placeholder="Add a test question…"
              value={newQuestion}
              onChange={(e) => setNewQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
            />
            <button
              onClick={handleAdd}
              disabled={adding || !newQuestion.trim()}
              className="text-xs px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded font-medium disabled:opacity-40 transition-colors"
            >
              {adding ? '…' : 'Add'}
            </button>
          </div>
        </div>

        {/* Score summary + results */}
        <div className="col-span-2 flex flex-col gap-4">
          {avgRag !== null && (
            <div className="card p-4 flex items-center gap-6">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 font-medium mb-1">Avg RAG Score</p>
                <ScoreBar value={avgRag} />
              </div>
              <div className="flex items-center gap-1.5 text-[10px] font-medium text-brand-600 dark:text-brand-400 ml-auto">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-pulse" />
                Live · refreshes every 15s
              </div>
            </div>
          )}

          <div className="card overflow-hidden flex-1">
            <div className="grid grid-cols-4 table-header min-w-[520px]">
              <span className="col-span-2">Question</span>
              <span>RAG Score</span>
              <span>Faithfulness / Relevance</span>
            </div>
            {latestByQuery.length === 0 && (
              <p className="text-xs text-gray-400 dark:text-gray-500 px-4 py-6">
                No results yet. Ingest a document to trigger evaluation.
              </p>
            )}
            {latestByQuery.map((e, i) => (
              <div key={i} className="grid grid-cols-4 table-row min-w-[520px]">
                <span className="col-span-2 text-xs text-gray-700 dark:text-gray-300 truncate pr-4" title={e.query}>{e.query}</span>
                <div>{e.rag_score ? <ScoreBar value={parseFloat(e.rag_score)} /> : <span className="text-gray-400">—</span>}</div>
                <div className="flex flex-col gap-1">
                  {e.faithfulness && (
                    <div className="flex items-center gap-1">
                      <span className="text-[9px] text-gray-400 w-10 flex-shrink-0">faith</span>
                      <ScoreBar value={parseFloat(e.faithfulness)} />
                    </div>
                  )}
                  {e.relevance && (
                    <div className="flex items-center gap-1">
                      <span className="text-[9px] text-gray-400 w-10 flex-shrink-0">rel</span>
                      <ScoreBar value={parseFloat(e.relevance)} />
                    </div>
                  )}
                  {!e.faithfulness && !e.relevance && <span className="text-gray-400 text-xs">—</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
