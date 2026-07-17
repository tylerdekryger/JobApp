import { Suspense } from "react";

import { JobCard } from "@/components/JobCard";
import { SearchControls } from "@/components/SearchControls";
import { listCompanies, searchJobs } from "@/lib/api";
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

export default async function HomePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const params: JobSearchParams = {
    q: pickString(sp.q),
    location: pickString(sp.location),
    company_id: pickNumber(sp.company_id),
    posted_since_days: pickNumber(sp.posted_since_days),
    limit: 25,
  };

  let jobs, companies;
  let error: string | null = null;
  try {
    [jobs, companies] = await Promise.all([searchJobs(params), listCompanies()]);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

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

      {jobs && (
        <>
          <div className="flex items-baseline justify-between">
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {jobs.total.toLocaleString()} job{jobs.total === 1 ? "" : "s"} match
              {params.q ? ` "${params.q}"` : ""}
            </p>
          </div>
          {jobs.items.length === 0 ? (
            <div className="card p-8 text-center" style={{ color: "var(--muted)" }}>
              No jobs match your filters. Try loosening the search or adding more sources.
            </div>
          ) : (
            <div className="grid gap-3">
              {jobs.items.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
