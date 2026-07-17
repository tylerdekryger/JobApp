"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  createSource,
  deleteSource,
  listSources,
  syncSource,
  type SourceSummary,
  type SyncResult,
} from "@/lib/api";

function formatDateTime(iso: string | null): string {
  if (!iso) return "never";
  const date = new Date(iso);
  const now = Date.now();
  const diffMs = now - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSources();
      setSources(data.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 6000);
    return () => clearTimeout(t);
  }, [flash]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    try {
      const created = await createSource(url.trim(), companyName.trim() || undefined);
      setUrl("");
      setCompanyName("");
      await refresh();
      // Auto-sync fresh sources so the user immediately sees jobs.
      await handleSync(created.id, { silent: true });
      setFlash({ kind: "ok", msg: `Added ${created.company_name} and synced.` });
    } catch (e) {
      setFlash({ kind: "err", msg: e instanceof Error ? e.message : String(e) });
    }
  }

  async function handleSync(id: number, opts: { silent?: boolean } = {}) {
    setBusyId(id);
    try {
      const result: SyncResult = await syncSource(id);
      if (!opts.silent) {
        setFlash({
          kind: "ok",
          msg: `Sync complete: ${result.jobs_found} found · ${result.jobs_added} added · ${result.jobs_updated} updated · ${result.jobs_removed} removed (${result.duration_seconds.toFixed(1)}s)`,
        });
      }
      await refresh();
    } catch (e) {
      setFlash({ kind: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!confirm(`Delete ${name} and all of its jobs? This cannot be undone.`)) return;
    setBusyId(id);
    try {
      await deleteSource(id);
      await refresh();
      setFlash({ kind: "ok", msg: `Deleted ${name}.` });
    } catch (e) {
      setFlash({ kind: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Sources</h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            Career boards being pulled in. Adding one syncs it immediately.
          </p>
        </div>
        <Link href="/" className="text-sm underline" style={{ color: "var(--accent)" }}>
          ← Back to search
        </Link>
      </div>

      <form onSubmit={handleAdd} className="card p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://boards.greenhouse.io/<board-token>"
            className="flex-1 rounded-lg border px-3 py-2 bg-transparent"
            style={{ borderColor: "var(--border)" }}
          />
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Company name (optional)"
            className="sm:w-56 rounded-lg border px-3 py-2 bg-transparent"
            style={{ borderColor: "var(--border)" }}
          />
          <button
            type="submit"
            className="rounded-lg px-4 py-2 text-white font-medium whitespace-nowrap"
            style={{ background: "var(--accent)" }}
          >
            Add + Sync
          </button>
        </div>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          Currently supports Greenhouse boards (<code>boards.greenhouse.io/&lt;token&gt;</code>).
        </p>
      </form>

      {flash && (
        <div
          className="card p-3 text-sm"
          style={{
            color: flash.kind === "ok" ? "#16a34a" : "#dc2626",
            borderColor: flash.kind === "ok" ? "#16a34a55" : "#dc262655",
          }}
        >
          {flash.msg}
        </div>
      )}

      {error && (
        <div className="card p-3 text-sm" style={{ color: "#dc2626" }}>
          Could not load sources: {error}
        </div>
      )}

      {loading ? (
        <div className="card p-6 text-sm" style={{ color: "var(--muted)" }}>
          Loading sources…
        </div>
      ) : sources.length === 0 ? (
        <div className="card p-8 text-center text-sm" style={{ color: "var(--muted)" }}>
          No sources yet. Paste a Greenhouse board URL above to get started.
        </div>
      ) : (
        <div className="grid gap-3">
          {sources.map((s) => (
            <div key={s.id} className="card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold">{s.company_name}</h2>
                    <span
                      className="text-xs rounded-full px-2 py-0.5"
                      style={{ background: "var(--bg)", color: "var(--muted)", border: "1px solid var(--border)" }}
                    >
                      {s.provider}
                    </span>
                    <span
                      className="text-xs rounded-full px-2 py-0.5"
                      style={{
                        background: s.status === "active" ? "#16a34a22" : "var(--bg)",
                        color: s.status === "active" ? "#16a34a" : "var(--muted)",
                        border: `1px solid ${s.status === "active" ? "#16a34a55" : "var(--border)"}`,
                      }}
                    >
                      {s.status}
                    </span>
                  </div>
                  <div className="text-sm mt-1" style={{ color: "var(--muted)" }}>
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                      style={{ color: "var(--accent)" }}
                    >
                      {s.source_url}
                    </a>
                  </div>
                  <div className="text-sm mt-2" style={{ color: "var(--muted)" }}>
                    <strong style={{ color: "var(--text)" }}>{s.active_job_count.toLocaleString()}</strong>{" "}
                    active job{s.active_job_count === 1 ? "" : "s"} · last synced {formatDateTime(s.last_successful_sync)}
                  </div>
                  {s.last_error && (
                    <div className="text-sm mt-2" style={{ color: "#dc2626" }}>
                      Last error: {s.last_error}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Link
                    href={`/?source_id=${s.id}`}
                    className="rounded-lg px-3 py-1.5 text-sm border"
                    style={{ borderColor: "var(--border)" }}
                  >
                    View jobs
                  </Link>
                  <button
                    onClick={() => handleSync(s.id)}
                    disabled={busyId === s.id}
                    className="rounded-lg px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    style={{ background: "var(--accent)" }}
                  >
                    {busyId === s.id ? "Working…" : "Sync now"}
                  </button>
                  <button
                    onClick={() => handleDelete(s.id, s.company_name)}
                    disabled={busyId === s.id}
                    className="rounded-lg px-3 py-1.5 text-sm border disabled:opacity-50"
                    style={{ borderColor: "#dc262655", color: "#dc2626" }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
