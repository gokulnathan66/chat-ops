import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'LLMOps — AI Interface',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
          <span className="font-bold text-white">LLMOps</span>
          <Link href="/" className="text-gray-400 hover:text-white transition-colors">Chat</Link>
          <Link href="/hitl" className="text-gray-400 hover:text-white transition-colors">HITL Queue</Link>
          <Link href="/ingestion" className="text-gray-400 hover:text-white transition-colors">Ingestion</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
