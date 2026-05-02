'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from '@/components/ThemeProvider';

const navItems = [
  { href: '/', label: 'Chat' },
];

export default function NavSidebar() {
  const path = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <div className="w-56 flex-shrink-0 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col h-screen">
      <div className="px-4 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-gray-900 dark:bg-brand-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-[11px] font-bold">L</span>
          </div>
          <div>
            <span className="font-semibold text-gray-900 dark:text-gray-100 text-sm block leading-tight">LLMOps</span>
            <span className="text-[10px] text-gray-400 dark:text-gray-500 leading-tight">AI Interface</span>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-2 py-3">
        <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest px-2 mb-1.5">Interface</p>
        {navItems.map(({ href, label }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center px-2.5 py-1.5 rounded-md text-sm transition-colors mb-0.5 ${
                active
                  ? 'bg-gray-900 dark:bg-brand-600 text-white font-medium'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100 font-normal'
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="px-2 pb-2">
        <button
          onClick={toggle}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
        >
          <span>Theme</span>
          <span className="text-sm leading-none">{theme === 'dark' ? '☀' : '🌙'}</span>
        </button>
      </div>
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-brand-500 to-purple-500 flex-shrink-0" />
          <span className="text-xs text-gray-600 dark:text-gray-400 truncate">LLMOps AI</span>
        </div>
      </div>
    </div>
  );
}
