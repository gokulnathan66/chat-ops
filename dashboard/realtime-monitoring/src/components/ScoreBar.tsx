interface Props { value: number; width?: string; }

export function ScoreBar({ value, width = 'w-16' }: Props) {
  return (
    <div className="flex items-center gap-2">
      <div className={`${width} bg-gray-200 dark:bg-gray-700 rounded-sm h-1 flex-shrink-0`}>
        <div
          className="bg-brand-600 dark:bg-brand-500 h-1 rounded-sm transition-all duration-300"
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
        />
      </div>
      <span className="font-mono text-xs text-gray-700 dark:text-gray-300 tabular-nums">
        {value.toFixed(2)}
      </span>
    </div>
  );
}
