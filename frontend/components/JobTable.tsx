"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { analyzeJob, type Job } from "@/lib/api";

type SortKey = "added_desc" | "added_asc" | "posted_desc" | "posted_asc";

interface Props {
  jobs: Job[];
  currentSort: SortKey;
}

function toSnippet(html: string, max = 220): string {
  // Descriptions can arrive as HTML with double-encoded entities. Decode enough to make a
  // readable one-line summary.
  const once = html.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&#39;/g, "'").replace(/&quot;/g, '"');
  const stripped = once.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  return stripped.length > max ? stripped.slice(0, max).trimEnd() + "…" : stripped;
}

function relativeShort(iso: string | null): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

function isoToShort(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

type AnalysisState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; fit: string; gap: string }
  | { kind: "error"; message: string };

export function JobTable({ jobs, currentSort }: Props) {
  const params = useSearchParams();
  const [analyses, setAnalyses] = useState<Record<number, AnalysisState>>({});

  function sortLink(column: "added" | "posted"): { href: string; indicator: string; active: boolean } {
    const isActive = currentSort.startsWith(column);
    // Toggle direction if already active on this column; otherwise start descending (recent-first).
    let next: SortKey;
    if (!isActive) {
      next = (column === "added" ? "added_desc" : "posted_desc");
    } else {
      next = currentSort.endsWith("_desc")
        ? ((column + "_asc") as SortKey)
        : ((column + "_desc") as SortKey);
    }
    const usp = new URLSearchParams(params.toString());
    usp.set("sort", next);
    usp.delete("offset");
    const indicator = isActive ? (currentSort.endsWith("_desc") ? " ↓" : " ↑") : "";
    return { href: `/?${usp.toString()}`, indicator, active: isActive };
  }

  const addedSort = sortLink("added");
  const postedSort = sortLink("posted");

  async function runAnalysis(jobId: number) {
    setAnalyses((s) => ({ ...s, [jobId]: { kind: "loading" } }));
    try {
      const result = await analyzeJob(jobId);
      setAnalyses((s) => ({
        ...s,
        [jobId]: { kind: "done", fit: result.fit_summary, gap: result.gap_summary },
      }));
    } catch (e) {
      setAnalyses((s) => ({
        ...s,
        [jobId]: { kind: "error", message: String(e).replace(/^Error:\s*/, "") },
      }));
    }
  }

  async function analyzeAllVisible() {
    for (const job of jobs) {
      const already = analyses[job.id]?.kind === "done" || (!!job.fit_summary && !job.analysis_is_stale);
      if (already) continue;
      // eslint-disable-next-line no-await-in-loop -- deliberate sequential pacing to avoid rate limits
      await runAnalysis(job.id);
    }
  }

  const analyzedCount = jobs.filter((j) => {
    const local = analyses[j.id];
    return (local && local.kind === "done") || (j.fit_summary && !j.analysis_is_stale);
  }).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {analyzedCount}/{jobs.length} rows analyzed
        </p>
        <button
          type="button"
          onClick={analyzeAllVisible}
          disabled={analyzedCount === jobs.length}
          className="rounded-lg px-3 py-1.5 text-sm font-medium border transition-opacity"
          style={{
            borderColor: "var(--accent)",
            color: "var(--accent)",
            opacity: analyzedCount === jobs.length ? 0.4 : 1,
          }}
        >
          Analyze all visible ({jobs.length - analyzedCount} left)
        </button>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr style={{ background: "var(--bg)" }}>
              <Th>
                <Link href={addedSort.href} className="hover:underline" style={{ color: addedSort.active ? "var(--accent)" : "inherit" }}>
                  Added{addedSort.indicator}
                </Link>
              </Th>
              <Th>
                <Link href={postedSort.href} className="hover:underline" style={{ color: postedSort.active ? "var(--accent)" : "inherit" }}>
                  Posted{postedSort.indicator}
                </Link>
              </Th>
              <Th>Company</Th>
              <Th>Role</Th>
              <Th>Location</Th>
              <Th>Link</Th>
              <Th className="min-w-[220px]">Overview</Th>
              <Th className="min-w-[220px]">Fit</Th>
              <Th className="min-w-[220px]">Gaps</Th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const state = analyses[job.id];
              const cached = job.fit_summary && job.gap_summary
                ? { fit: job.fit_summary, gap: job.gap_summary }
                : null;
              const analysis =
                state?.kind === "done"
                  ? { fit: state.fit, gap: state.gap }
                  : cached && !job.analysis_is_stale
                    ? cached
                    : null;
              return (
                <tr
                  key={job.id}
                  className="align-top"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  <Td className="whitespace-nowrap text-xs">
                    <div>{relativeShort(job.reopened_at ?? job.first_seen_at)}</div>
                    {job.reopened_at && (
                      <div
                        className="mt-1 inline-block text-[10px] font-medium rounded px-1.5 py-0.5"
                        style={{ background: "#eab30822", color: "#a16207", border: "1px solid #eab30855" }}
                        title={`Originally first seen ${new Date(job.first_seen_at).toLocaleDateString()}`}
                      >
                        Reposted · orig {isoToShort(job.first_seen_at)}
                      </div>
                    )}
                  </Td>
                  <Td className="whitespace-nowrap text-xs" style={{ color: "var(--muted)" }}>
                    {relativeShort(job.posted_at)}
                  </Td>
                  <Td className="whitespace-nowrap">{job.company_name ?? "—"}</Td>
                  <Td className="min-w-[220px]">
                    <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                      {job.title}
                    </Link>
                    {job.department && (
                      <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                        {job.department}
                      </div>
                    )}
                  </Td>
                  <Td className="max-w-[200px]">
                    <div className="flex items-center gap-1.5">
                      <RemoteDot type={job.remote_type} />
                      <span>{job.location ?? "—"}</span>
                    </div>
                  </Td>
                  <Td>
                    <a
                      href={job.canonical_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 hover:underline"
                      style={{ color: "var(--accent)" }}
                    >
                      Apply ↗
                    </a>
                  </Td>
                  <Td>
                    <p style={{ color: "var(--muted)" }} className="leading-snug">
                      {toSnippet(job.description_clean || job.description)}
                    </p>
                  </Td>
                  <Td>
                    <AnalysisCell
                      state={state}
                      cached={cached}
                      stale={job.analysis_is_stale}
                      side="fit"
                      onAnalyze={() => runAnalysis(job.id)}
                    />
                  </Td>
                  <Td>
                    <AnalysisCell
                      state={state}
                      cached={cached}
                      stale={job.analysis_is_stale}
                      side="gap"
                      onAnalyze={() => runAnalysis(job.id)}
                    />
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-left font-medium px-3 py-2 text-xs uppercase tracking-wide ${className}`}
      style={{ color: "var(--muted)" }}
    >
      {children}
    </th>
  );
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-3 ${className}`}>{children}</td>;
}

function RemoteDot({ type }: { type: string | null }) {
  const colors: Record<string, string> = {
    remote: "#16a34a",
    hybrid: "#eab308",
    onsite: "#64748b",
    unknown: "#cbd5e1",
  };
  const c = colors[type ?? "unknown"] ?? "#cbd5e1";
  return (
    <span
      className="inline-block h-2 w-2 rounded-full flex-shrink-0"
      style={{ background: c }}
      title={type ?? "unknown"}
    />
  );
}

function AnalysisCell({
  state,
  cached,
  stale,
  side,
  onAnalyze,
}: {
  state: AnalysisState | undefined;
  cached: { fit: string; gap: string } | null;
  stale: boolean;
  side: "fit" | "gap";
  onAnalyze: () => void;
}) {
  if (state?.kind === "loading") {
    return <span style={{ color: "var(--muted)" }} className="text-xs">Analyzing…</span>;
  }
  if (state?.kind === "error") {
    return (
      <div className="text-xs" style={{ color: "#dc2626" }}>
        {state.message}
        <button onClick={onAnalyze} className="ml-2 underline">
          retry
        </button>
      </div>
    );
  }
  if (state?.kind === "done") {
    return <p className="leading-snug">{side === "fit" ? state.fit : state.gap}</p>;
  }
  if (cached && !stale) {
    return <p className="leading-snug">{side === "fit" ? cached.fit : cached.gap}</p>;
  }
  // No fresh analysis yet — show the button once (in the "fit" cell) and a hint in the other.
  if (side === "fit") {
    return (
      <button
        onClick={onAnalyze}
        className="rounded border px-2 py-1 text-xs font-medium hover:opacity-90"
        style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
      >
        {stale ? "Re-analyze" : "Analyze"}
      </button>
    );
  }
  if (cached && stale) {
    return (
      <p className="text-xs leading-snug" style={{ color: "var(--muted)" }}>
        <em>(stale)</em> {side === "fit" ? cached.fit : cached.gap}
      </p>
    );
  }
  return <span style={{ color: "var(--muted)" }} className="text-xs">—</span>;
}
