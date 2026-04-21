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
