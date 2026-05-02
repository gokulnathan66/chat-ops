import IngestionPanel from '@/components/IngestionPanel';

export default function IngestionPage() {
  return (
    <div className="space-y-6">
      <div className="page-header">
        <p className="page-eyebrow">Data</p>
        <h1 className="page-title">Document Ingestion</h1>
        <p className="page-subtitle">
          Upload a file directly or provide an S3 key to ingest into the Qdrant vector store.
          Job status updates live — no more guessing if it worked.
        </p>
      </div>
      <IngestionPanel />
    </div>
  );
}
