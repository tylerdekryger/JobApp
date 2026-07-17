import Link from "next/link";
import { notFound } from "next/navigation";

import { getJob } from "@/lib/api";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

function decodeHtmlEntities(input: string): string {
  return input
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function formatDate(iso: string | null): string {
  if (!iso) return "unknown";
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default async function JobPage({ params }: Props) {
  const { id } = await params;
  let job;
  try {
    job = await getJob(id);
  } catch {
    notFound();
  }

  // Prefer the cleaned description (with per-source boilerplate stripped). Greenhouse returns HTML
  // with double-encoded entities.
  const descriptionHtml = decodeHtmlEntities(job.description_clean || job.description);
  const hadBoilerplate = job.description_clean && job.description_clean !== job.description;

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm underline" style={{ color: "var(--accent)" }}>
        ← Back to search
      </Link>

      <header className="card p-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">{job.title}</h1>
            <p className="mt-1" style={{ color: "var(--muted)" }}>
              {job.company_name ?? "Unknown company"}
              {job.department ? ` · ${job.department}` : ""}
            </p>
          </div>
          <a
            href={job.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg px-4 py-2 text-white font-medium whitespace-nowrap"
            style={{ background: "var(--accent)" }}
          >
            Apply on company site ↗
          </a>
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
          <div>
            <dt style={{ color: "var(--muted)" }}>Location</dt>
            <dd className="font-medium">{job.location ?? "Not specified"}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)" }}>Remote</dt>
            <dd className="font-medium capitalize">{job.remote_type ?? "unknown"}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)" }}>Posted</dt>
            <dd className="font-medium">{formatDate(job.posted_at)}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)" }}>First seen</dt>
            <dd className="font-medium">{formatDate(job.first_seen_at)}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)" }}>Status</dt>
            <dd className="font-medium capitalize">{job.status}</dd>
          </div>
        </dl>
      </header>

      {hadBoilerplate && (
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          Company boilerplate (About / Who we are) has been hidden for readability.
        </p>
      )}
      <article className="card p-6 job-body" dangerouslySetInnerHTML={{ __html: descriptionHtml }} />
    </div>
  );
}
