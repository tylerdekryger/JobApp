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

export function JobCard({ job }: { job: Job }) {
  return (
    <Link href={`/jobs/${job.id}`} className="block">
      <article
        className="card p-5 transition-transform hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">{job.title}</h2>
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
