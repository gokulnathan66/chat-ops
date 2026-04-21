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
