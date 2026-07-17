import Link from "next/link";
import { Suspense } from "react";

import { FacetPanel } from "@/components/FacetPanel";
import { JobCard } from "@/components/JobCard";
import { SearchControls } from "@/components/SearchControls";
import { getFacets, listCompanies, searchJobs } from "@/lib/api";
import type { JobSearchParams } from "@/lib/api";

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
    if (k === key) continue;
    const val = pickString(v);
    if (val) usp.set(k, val);
  }
  const q = usp.toString();
  return q ? `/?${q}` : "/";
}

export default async function HomePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const params: JobSearchParams = {
    q: pickString(sp.q),
    location: pickString(sp.location),
    department: pickString(sp.department),
    company_id: pickNumber(sp.company_id),
    posted_since_days: pickNumber(sp.posted_since_days),
    limit: 25,
  };

  let jobs, companies, facets;
  let error: string | null = null;
  try {
    [jobs, companies, facets] = await Promise.all([
      searchJobs(params),
      listCompanies(),
      getFacets(params),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const companiesById: Record<string, string> = {};
  for (const c of companies?.items ?? []) {
    companiesById[String(c.id)] = c.name;
  }

  const activeCompanyName =
    params.company_id !== undefined ? companiesById[String(params.company_id)] : undefined;

  return (
    <div className="space-y-6">
      <Suspense fallback={<div className="card p-4" style={{ color: "var(--muted)" }}>Loading filters…</div>}>
        <SearchControls companies={companies?.items ?? []} />
      </Suspense>

      {error && (
        <div className="card p-4" style={{ color: "#dc2626" }}>
          Could not reach the API: {error}. Is the backend running on{" "}
          <code>{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</code>?
        </div>
      )}

      {jobs && facets && (
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <Suspense fallback={<div className="card p-4" style={{ color: "var(--muted)" }}>Loading facets…</div>}>
            <FacetPanel
              facets={facets}
              activeLocation={params.location ?? null}
              activeCompanyId={params.company_id !== undefined ? String(params.company_id) : null}
              companiesById={companiesById}
            />
          </Suspense>
          <div className="space-y-4">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <p className="text-sm" style={{ color: "var(--muted)" }}>
                {jobs.total.toLocaleString()} job{jobs.total === 1 ? "" : "s"} match
                {params.q ? ` "${params.q}"` : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                {params.department && (
                  <ActiveFilterChip
                    label={`Department: ${params.department}`}
                    removeHref={buildRemoveHref(sp, "department")}
                  />
                )}
                {params.location && (
                  <ActiveFilterChip
                    label={`Location: ${params.location}`}
                    removeHref={buildRemoveHref(sp, "location")}
                  />
                )}
                {activeCompanyName && (
                  <ActiveFilterChip
                    label={`Company: ${activeCompanyName}`}
                    removeHref={buildRemoveHref(sp, "company_id")}
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
              <div className="grid gap-3">
                {jobs.items.map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
