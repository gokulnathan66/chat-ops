'use client';
import { Session } from '@/lib/api';

interface Props {
  sessions: Session[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

export default function SessionList({ sessions, selectedId, onSelect, onNewChat }: Props) {
  return (
    <div className="w-60 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 h-full flex flex-col flex-shrink-0">
      <div className="px-3 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest leading-none">Sessions</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{sessions.length} session{sessions.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={onNewChat}
          className="flex-shrink-0 px-2.5 py-1.5 rounded-md bg-gray-900 dark:bg-brand-600 text-white text-xs font-semibold hover:bg-gray-700 dark:hover:bg-brand-500 transition-colors"
        >
          + New
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-px">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-400 dark:text-gray-500 px-2 py-4 text-center">
            No sessions yet.<br />Start a new chat.
          </p>
        )}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => onSelect(s.session_id)}
            className={`w-full text-left px-2.5 py-2 rounded-md text-xs transition-colors ${
              selectedId === s.session_id
                ? 'bg-gray-900 dark:bg-brand-600 text-white font-medium'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
            }`}
          >
            <span className="block font-mono truncate">{s.session_id.slice(0, 22)}…</span>
            <span className={`block text-[10px] mt-0.5 ${selectedId === s.session_id ? 'opacity-70' : 'opacity-50'}`}>
              {s.turn_count} turn{s.turn_count !== 1 ? 's' : ''} · {s.status}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
