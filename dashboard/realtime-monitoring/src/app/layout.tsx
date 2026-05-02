import type { Metadata } from 'next';
import NavSidebar from '@/components/NavSidebar';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = { title: 'LLMOps — Monitoring' };

const themeScript = `
try {
  const t = localStorage.getItem('theme') ?? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  if (t === 'dark') document.documentElement.classList.add('dark');
} catch(e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="bg-surface dark:bg-gray-950 text-gray-900 dark:text-gray-100">
        <ThemeProvider>
          <div className="flex h-screen bg-surface dark:bg-gray-950">
            <NavSidebar />
            <main className="flex-1 overflow-y-auto">
              <div className="p-6 max-w-6xl">
                {children}
              </div>
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
