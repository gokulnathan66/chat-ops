'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startIngestion,
  uploadAndIngest,
  getIngestionStatus,
  getIngestionHistory,
  type IngestionJob,
  type StartIngestionResult,
} from '@/lib/api';

type Tab = 'upload' | 's3key';
type JobStatus = IngestionJob['status'];

const STATUS_LABEL: Record<JobStatus, string> = {
  started: 'Queued',
  running: 'Processing…',
  completed: 'Completed',
  error: 'Failed',
};

const STATUS_COLOR: Record<JobStatus, string> = {
  started:   'text-yellow-600 dark:text-yellow-400',
  running:   'text-blue-600 dark:text-blue-400',
  completed: 'text-green-600 dark:text-green-400',
  error:     'text-red-600 dark:text-red-400',
};

const STATUS_DOT: Record<JobStatus, string> = {
  started:   'bg-yellow-400',
  running:   'bg-blue-400 animate-pulse',
  completed: 'bg-green-400',
  error:     'bg-red-400',
};

const ALLOWED = ['.pdf', '.txt', '.csv'];
const POLL_MS = 3000;

function fmt(iso?: string) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function StatusPill({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${STATUS_COLOR[status]}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

function JobCard({ job }: { job: IngestionJob }) {
  const s3ShortKey = job.s3_key?.split('/').pop() ?? job.s3_key;
  return (
    <div className="card p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{s3ShortKey}</p>
          <p className="text-xs text-gray-400 font-mono truncate">{job.s3_key}</p>
        </div>
        <StatusPill status={job.status} />
      </div>
      {(job.status === 'completed') && (
        <div className="flex gap-4 text-xs text-gray-600 dark:text-gray-400 pt-1 border-t border-gray-100 dark:border-gray-800">
          <span><b className="text-gray-900 dark:text-gray-100">{job.chunks_indexed ?? 0}</b> chunks indexed</span>
          <span><b className="text-gray-900 dark:text-gray-100">{job.files_processed ?? 0}</b> files</span>
          {Number(job.files_skipped) > 0 && <span>{job.files_skipped} skipped</span>}
          {Number(job.files_errored) > 0 && <span className="text-red-500">{job.files_errored} errors</span>}
        </div>
      )}
      <p className="text-[11px] text-gray-400">Started {fmt(job.created_at)}{job.completed_at ? ` · Finished ${fmt(job.completed_at)}` : ''}</p>
    </div>
  );
}

function DropZone({ onFile }: { onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    if (!files?.length) return;
    onFile(files[0]);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }, []);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={`relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed
        cursor-pointer select-none transition-colors p-8
        ${dragging
          ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-gray-50 dark:bg-gray-800/40'
        }`}
    >
      <svg className="w-8 h-8 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round"
          d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        <span className="font-semibold text-gray-700 dark:text-gray-200">Click to browse</span> or drag &amp; drop
      </p>
      <p className="text-xs text-gray-400">{ALLOWED.join(', ')} · max 50 MB</p>
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED.join(',')}
        className="sr-only"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}

export default function IngestionPanel() {
  const [tab, setTab] = useState<Tab>('upload');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [s3Key, setS3Key] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeJob, setActiveJob] = useState<IngestionJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [history, setHistory] = useState<IngestionJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const clearPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

  useEffect(() => () => clearPoll(), []);

  const startPolling = (jobId: string) => {
    clearPoll();
    pollRef.current = setInterval(async () => {
      try {
        const job = await getIngestionStatus(jobId);
        setActiveJob(job);
        if (job.status === 'completed' || job.status === 'error') {
          clearPoll();
          loadHistory();
        }
      } catch { /* keep polling */ }
    }, POLL_MS);
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try { setHistory(await getIngestionHistory(10)); } catch { /* noop */ } finally { setHistoryLoading(false); }
  };

  useEffect(() => { loadHistory(); }, []);

  const handleResult = (result: StartIngestionResult) => {
    setActiveJob({
      session_id: result.job_id,
      sk: 'ingestion_job',
      eval_type: 'ingestion_job',
      status: 'started',
      s3_key: result.s3_key,
      created_at: new Date().toISOString(),
    });
    startPolling(result.job_id);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setActiveJob(null);
    setSubmitting(true);
    try {
      if (tab === 'upload') {
        if (!selectedFile) return;
        const result = await uploadAndIngest(selectedFile);
        setSelectedFile(null);
        handleResult(result);
      } else {
        if (!s3Key.trim()) return;
        const result = await startIngestion(s3Key.trim());
        setS3Key('');
        handleResult(result);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = tab === 'upload' ? !!selectedFile : !!s3Key.trim();

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Tab switcher */}
      <div className="card p-6 space-y-5">
        <div className="flex gap-1 p-1 rounded-lg bg-gray-100 dark:bg-gray-800 w-fit">
          {(['upload', 's3key'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError(null); }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors
                ${tab === t
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}`}
            >
              {t === 'upload' ? 'Upload File' : 'S3 Key'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === 'upload' ? (
            <div className="space-y-3">
              <DropZone onFile={(f) => { setSelectedFile(f); setError(null); }} />
              {selectedFile && (
                <div className="flex items-center justify-between rounded-md bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                    <span className="text-sm text-gray-700 dark:text-gray-200 truncate font-medium">{selectedFile.name}</span>
                    <span className="text-xs text-gray-400 shrink-0">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <button type="button" onClick={() => setSelectedFile(null)} className="btn-ghost py-0.5 px-1.5 text-xs">✕</button>
                </div>
              )}
            </div>
          ) : (
            <div>
              <label className="label">S3 Object Key</label>
              <input
                value={s3Key}
                onChange={(e) => setS3Key(e.target.value)}
                placeholder="documents/my-file.pdf"
                className="input"
              />
              <p className="mt-1 text-xs text-gray-400">The S3 object key — not the full URL.</p>
            </div>
          )}

          <button type="submit" disabled={submitting || !canSubmit} className="btn-primary">
            {submitting
              ? (tab === 'upload' ? 'Uploading…' : 'Starting…')
              : (tab === 'upload' ? 'Upload & Ingest' : '+ Start Ingestion')}
          </button>
        </form>

        {error && <div className="error-box">{error}</div>}
      </div>

      {/* Active job status */}
      {activeJob && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Current Job</h3>
          <JobCard job={activeJob} />
          {(activeJob.status === 'started' || activeJob.status === 'running') && (
            <p className="text-xs text-gray-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
              Checking every {POLL_MS / 1000}s…
            </p>
          )}
        </div>
      )}

      {/* Job history */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Recent Jobs</h3>
          <button onClick={loadHistory} className="btn-ghost text-xs py-1">Refresh</button>
        </div>
        {historyLoading ? (
          <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-sm text-gray-400 py-4 text-center">No ingestion jobs yet.</p>
        ) : (
          <div className="space-y-2">
            {history.map((job) => <JobCard key={job.session_id} job={job} />)}
          </div>
        )}
      </div>
    </div>
  );
}
