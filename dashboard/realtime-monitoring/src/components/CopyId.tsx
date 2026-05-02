'use client';
import { useState } from 'react';

interface Props {
  id: string;
  display?: string;
}

export function CopyId({ id, display }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(id).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      className="group flex items-center gap-1.5 font-mono text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors text-left"
      title={id}
    >
      <span className="truncate">{display ?? (id.slice(0, 16) + '…')}</span>
      <span className={`flex-shrink-0 text-[10px] transition-all ${
        copied
          ? 'text-brand-600 dark:text-brand-400 opacity-100'
          : 'text-brand-300 dark:text-brand-600 opacity-0 group-hover:opacity-100'
      }`}>
        {copied ? '✓' : '⎘'}
      </span>
    </button>
  );
}
