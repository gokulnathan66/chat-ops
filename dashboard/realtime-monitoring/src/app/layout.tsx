import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = { title: 'LLMOps — Monitoring' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
          <span className="font-bold text-white">LLMOps Monitor</span>
          <Link href="/" className="text-gray-400 hover:text-white transition-colors">Overview</Link>
          <Link href="/evals" className="text-gray-400 hover:text-white transition-colors">RAG Evals</Link>
          <Link href="/golden" className="text-gray-400 hover:text-white transition-colors">Golden Dataset</Link>
          <Link href="/pca" className="text-gray-400 hover:text-white transition-colors">PCA</Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
