import Link from "next/link";
import { Suspense } from "react";

import { JobTable } from "@/components/JobTable";
import { Pagination } from "@/components/Pagination";
import { SearchControls } from "@/components/SearchControls";
import { searchJobs } from "@/lib/api";
import type { JobSearchParams } from "@/lib/api";

// Only remote-eligible roles are ever surfaced. Onsite and hybrid jobs never appear in results.
const ALWAYS_ON_REMOTE_TYPES = "remote,unknown";
const PAGE_SIZE = 50;
const VALID_SORTS = new Set(["added_desc", "added_asc", "posted_desc", "posted_asc"]);

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function pickString(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

function pickNumber(v: string | string[] | undefined): number | undefined {
  const s = pickString(v);
  if (!s) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

function ActiveFilterChip({ label, removeHref }: { label: string; removeHref: string }) {
  return (
    <Link
      href={removeHref}
      className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs border"
      style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
    >
      {label}
      <span aria-hidden>×</span>
    </Link>
  );
}

function buildRemoveHref(sp: Record<string, string | string[] | undefined>, key: string): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (k === key || k === "offset") continue;
    const val = pickString(v);
    if (val) usp.set(k, val);
  }
  const q = usp.toString();
  return q ? `/?${q}` : "/";
}

export default async function HomePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const rawSort = pickString(sp.sort) ?? "added_desc";
  const sort = (VALID_SORTS.has(rawSort) ? rawSort : "added_desc") as
    | "added_desc"
    | "added_asc"
    | "posted_desc"
    | "posted_asc";
  const offset = pickNumber(sp.offset) ?? 0;
  const params: JobSearchParams = {
    q: pickString(sp.q),
    remote_type: ALWAYS_ON_REMOTE_TYPES,
    title_contains: pickString(sp.title_contains),
    sort,
    limit: PAGE_SIZE,
    offset,
  };

  let jobs;
  let error: string | null = null;
  try {
    jobs = await searchJobs(params);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div className="space-y-6">
      <Suspense fallback={<div className="card p-4" style={{ color: "var(--muted)" }}>Loading filters…</div>}>
        <SearchControls />
      </Suspense>

      {error && (
        <div className="card p-4" style={{ color: "#dc2626" }}>
          Could not reach the API: {error}. Is the backend running on{" "}
          <code>{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</code>?
        </div>
      )}

      {jobs && (
        <div className="space-y-4">
          <div className="flex items-baseline justify-between gap-3 flex-wrap">
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {jobs.total.toLocaleString()} remote-eligible job{jobs.total === 1 ? "" : "s"} posted in the last 30 days
              {params.q ? ` matching "${params.q}"` : ""}
            </p>
            <div className="flex flex-wrap gap-2">
              {params.title_contains && (
                <ActiveFilterChip
                  label={`Role: ${params.title_contains}`}
                  removeHref={buildRemoveHref(sp, "title_contains")}
                />
              )}
            </div>
          </div>
          {jobs.items.length === 0 ? (
            <div className="card p-8 text-center" style={{ color: "var(--muted)" }}>
              No jobs match your filters. Try loosening the search or{" "}
              <Link href="/sources" className="underline" style={{ color: "var(--accent)" }}>
                add more sources
              </Link>
              .
            </div>
          ) : (
            <>
              <JobTable jobs={jobs.items} currentSort={sort} />
              <Suspense fallback={null}>
                <Pagination total={jobs.total} limit={jobs.limit} offset={jobs.offset} />
              </Suspense>
            </>
          )}
        </div>
      )}
    </div>
  );
}
