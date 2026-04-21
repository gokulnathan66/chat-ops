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
