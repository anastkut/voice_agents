import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = { title: "EffiGov Cases" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <header className="border-b border-neutral-200 bg-white">
          <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
            <span className="font-semibold">EffiGov</span>
            <Link href="/" className="text-sm text-neutral-600 hover:text-neutral-900">
              Dashboard
            </Link>
            <Link href="/call" className="text-sm text-neutral-600 hover:text-neutral-900">
              Simulate call
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
