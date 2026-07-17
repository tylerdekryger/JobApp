import Link from "next/link";
import type { Job } from "@/lib/api";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return "just now";
  const mins = Math.floor(diffSec / 60);
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"} ago`;
}

function toSnippet(html: string, maxChars = 220): string {
  const decoded = html
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
  const stripped = decoded.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (stripped.length <= maxChars) return stripped;
  return stripped.slice(0, maxChars).trimEnd() + "…";
}

function RemoteBadge({ type }: { type: string | null }) {
  if (!type || type === "unknown") return null;
  const styles: Record<string, { bg: string; fg: string; border: string; label: string }> = {
    remote:  { bg: "#16a34a22", fg: "#16a34a", border: "#16a34a55", label: "Remote" },
    hybrid:  { bg: "#eab30822", fg: "#a16207", border: "#eab30855", label: "Hybrid" },
    onsite:  { bg: "var(--bg)", fg: "var(--muted)", border: "var(--border)", label: "Onsite" },
  };
  const s = styles[type];
  if (!s) return null;
  return (
    <span
      className="text-xs rounded-full px-2 py-0.5"
      style={{ background: s.bg, color: s.fg, border: `1px solid ${s.border}` }}
    >
      {s.label}
    </span>
  );
}

export function JobCard({ job }: { job: Job }) {
  const snippetSource = job.description_clean || job.description;
  const snippet = snippetSource ? toSnippet(snippetSource) : "";
  return (
    <Link href={`/jobs/${job.id}`} className="block">
      <article className="card p-5 transition-transform hover:-translate-y-0.5 hover:shadow-md">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-semibold truncate">{job.title}</h2>
              <RemoteBadge type={job.remote_type} />
            </div>
            <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
              {job.company_name ?? "Unknown company"}
              {job.department ? ` · ${job.department}` : ""}
            </p>
          </div>
          <span
            className="text-xs whitespace-nowrap rounded-full px-2 py-1 flex-shrink-0"
            style={{ background: "var(--bg)", color: "var(--muted)", border: "1px solid var(--border)" }}
          >
            First seen {relativeTime(job.first_seen_at)}
          </span>
        </div>
        {snippet && (
          <p className="text-sm mt-3 line-clamp-2" style={{ color: "var(--muted)" }}>
            {snippet}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2 text-sm" style={{ color: "var(--muted)" }}>
          {job.location && (
            <span
              className="rounded-md px-2 py-0.5"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
            >
              📍 {job.location}
            </span>
          )}
          {job.employment_type && (
            <span
              className="rounded-md px-2 py-0.5"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
            >
              {job.employment_type}
            </span>
          )}
        </div>
      </article>
    </Link>
  );
}
