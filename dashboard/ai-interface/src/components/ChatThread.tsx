'use client';
import { useEffect, useRef, useState, KeyboardEvent } from 'react';
import { LocalTurn } from '@/lib/api';

interface Props {
  sessionId: string;
  turns: LocalTurn[];
  sending: boolean;
  loadingHistory: boolean;
  onSend: (query: string) => void;
  onEscalate: () => void;
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  );
}

function TurnItem({ turn }: { turn: LocalTurn }) {
  const [expandedDocs, setExpandedDocs] = useState(false);

  return (
    <div className="space-y-2 animate-fade-in">
      {/* User message */}
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-gray-900 dark:bg-gray-800 text-white rounded-lg px-4 py-2.5">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{turn.user_query}</p>
        </div>
      </div>

      {/* AI response or loading */}
      {turn.loading ? (
        <TypingIndicator />
      ) : (
        <div className="flex justify-start">
          <div className={`max-w-[80%] rounded-lg px-4 py-3 border ${
            turn.error
              ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700'
          }`}>
            {!turn.error && turn.route && (
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] font-semibold text-brand-600 dark:text-brand-400 uppercase tracking-wider">
                  {turn.route}
                </span>
                {turn.latency_ms > 0 && (
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">
                    {Math.round(turn.latency_ms)}ms
                    {turn.token_usage.input + turn.token_usage.output > 0 && (
                      <> · {turn.token_usage.input + turn.token_usage.output} tok</>
                    )}
                  </span>
                )}
              </div>
            )}
            <p className={`text-sm leading-relaxed whitespace-pre-wrap ${
              turn.error ? 'text-red-700 dark:text-red-400' : 'text-gray-800 dark:text-gray-200'
            }`}>
              {turn.ai_response}
            </p>

            {turn.retrieved_docs.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <button
                  onClick={() => setExpandedDocs((v) => !v)}
                  className="text-[11px] text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 font-medium flex items-center gap-1"
                >
                  <span>{expandedDocs ? '▼' : '▶'}</span>
                  {turn.retrieved_docs.length} source{turn.retrieved_docs.length !== 1 ? 's' : ''}
                </button>
                {expandedDocs && (
                  <div className="mt-2 space-y-1.5">
                    {turn.retrieved_docs.map((doc, i) => (
                      <div
                        key={i}
                        className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md px-3 py-2 text-[11px] text-gray-600 dark:text-gray-400"
                      >
                        {doc.title && (
                          <span className="font-semibold text-gray-900 dark:text-gray-200 mr-1.5">{doc.title}</span>
                        )}
                        {doc.score != null && (
                          <span className="font-mono text-gray-400 dark:text-gray-500 mr-1.5">
                            ({doc.score.toFixed(2)})
                          </span>
                        )}
                        {doc.text_snippet}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChatThread({ sessionId, turns, sending, loadingHistory, onSend, onEscalate }: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom whenever turns or sending changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, sending]);

  const handleSubmit = () => {
    const query = input.trim();
    if (!query || sending) return;
    setInput('');
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    onSend(query);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-grow textarea up to 5 lines
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex-shrink-0">
        <div>
          <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest leading-none mb-0.5">Session</p>
          <span className="text-xs font-mono text-gray-600 dark:text-gray-400">{sessionId}</span>
        </div>
        <button
          onClick={onEscalate}
          className="text-xs px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-medium"
        >
          Escalate to Human
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
        {loadingHistory ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-gray-400 dark:text-gray-500">Loading…</p>
          </div>
        ) : turns.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-1">
              <p className="text-sm text-gray-400 dark:text-gray-500">Send a message to start the conversation</p>
            </div>
          </div>
        ) : (
          turns.map((turn) => <TurnItem key={turn.sk} turn={turn} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3">
        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Message LLMOps AI… (Enter to send, Shift+Enter for newline)"
            rows={1}
            disabled={sending}
            className="flex-1 resize-none rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/10 disabled:opacity-50 transition-colors overflow-hidden leading-relaxed"
            style={{ minHeight: '38px', maxHeight: '120px' }}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || sending}
            className="flex-shrink-0 px-4 py-2 rounded-md bg-gray-900 dark:bg-brand-600 text-white text-sm font-semibold hover:bg-gray-700 dark:hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? (
              <span className="flex items-center gap-1.5">
                <span className="w-1 h-1 bg-white rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1 h-1 bg-white rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1 h-1 bg-white rounded-full animate-bounce [animation-delay:300ms]" />
              </span>
            ) : 'Send'}
          </button>
        </div>
        <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1.5 pl-0.5">
          Enter ↵ to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
