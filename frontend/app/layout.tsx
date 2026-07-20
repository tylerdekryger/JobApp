import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job Intelligence",
  description: "Job discovery across company ATS platforms",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen" suppressHydrationWarning>
        <header className="border-b" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
          <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
            <Link href="/" className="font-semibold text-lg tracking-tight">
              Job Intelligence
            </Link>
            <nav className="flex items-center gap-5 text-sm">
              <Link href="/" className="hover:underline">
                Search
              </Link>
              <Link href="/sources" className="hover:underline">
                Sources
              </Link>
              <Link href="/profile" className="hover:underline">
                Profile
              </Link>
              <Link href="/digest" className="hover:underline">
                Digest
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
