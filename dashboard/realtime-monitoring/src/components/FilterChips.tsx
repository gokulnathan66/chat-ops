'use client';

export interface Chip<T> {
  label: string;
  value: T;
  count?: number;
}

interface Props<T extends string> {
  chips: Chip<T>[];
  active: T;
  onChange: (v: T) => void;
}

export function FilterChips<T extends string>({ chips, active, onChange }: Props<T>) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {chips.map((chip) => {
        const isActive = chip.value === active;
        return (
          <button
            key={String(chip.value)}
            onClick={() => onChange(chip.value)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium border transition-colors ${
              isActive
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            {chip.label}
            {chip.count !== undefined && (
              <span className={`px-1.5 py-px rounded text-[10px] font-semibold leading-none ${
                isActive
                  ? 'bg-white/20 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
              }`}>
                {chip.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
