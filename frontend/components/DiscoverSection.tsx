"use client";

import { useState } from "react";

import {
  createSource,
  extractCandidates,
  searchCandidates,
  syncSource,
  type DiscoverCandidate,
} from "@/lib/api";

type Mode = "search" | "paste";

interface AddState {
  running: boolean;
  done: number;
  total: number;
  log: { token: string; result: "added" | "skipped" | "error"; detail: string }[];
}

interface Props {
  onSourcesChanged: () => Promise<void> | void;
}

export function DiscoverSection({ onSourcesChanged }: Props) {
  const [mode, setMode] = useState<Mode>("search");
  const [query, setQuery] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<DiscoverCandidate[] | null>(null);
  const [totalSeen, setTotalSeen] = useState(0);
  const [filteredOut, setFilteredOut] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [add, setAdd] = useState<AddState | null>(null);

  async function runDiscover() {
    setLoading(true);
    setError(null);
    setCandidates(null);
    setSelected(new Set());
    setAdd(null);
    try {
      const resp =
        mode === "search"
          ? await searchCandidates(query.trim())
          : await extractCandidates(pasteText);
      setCandidates(resp.candidates);
      setTotalSeen(resp.total_tokens_seen);
      setFilteredOut(resp.filtered_out);
      // Preselect everything that isn't already registered so the user can just click Add.
      const preselect = new Set(
        resp.candidates.filter((c) => !c.already_registered).map((c) => c.token),
      );
      setSelected(preselect);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function toggle(token: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(token)) next.delete(token);
      else next.add(token);
      return next;
    });
  }

  async function addSelected() {
    if (!candidates) return;
    const toAdd = candidates.filter((c) => selected.has(c.token));
    if (toAdd.length === 0) return;

    setAdd({ running: true, total: toAdd.length, done: 0, log: [] });
    for (const cand of toAdd) {
      try {
        const created = await createSource(cand.source_url);
        try {
          const res = await syncSource(created.id);
          setAdd((s) =>
            s
              ? {
                  ...s,
                  done: s.done + 1,
                  log: [
                    ...s.log,
                    {
                      token: cand.token,
                      result: "added",
                      detail: `${created.company_name} — ${res.jobs_added} jobs`,
                    },
                  ],
                }
              : s,
          );
        } catch (syncErr) {
          setAdd((s) =>
            s
              ? {
                  ...s,
                  done: s.done + 1,
                  log: [
                    ...s.log,
                    {
                      token: cand.token,
                      result: "error",
                      detail: `added ${created.company_name} but sync failed: ${syncErr instanceof Error ? syncErr.message : String(syncErr)}`,
                    },
                  ],
                }
              : s,
          );
        }
      } catch (e) {
        setAdd((s) =>
          s
            ? {
                ...s,
                done: s.done + 1,
                log: [
                  ...s.log,
                  {
                    token: cand.token,
                    result: "error",
                    detail: e instanceof Error ? e.message : String(e),
                  },
                ],
              }
            : s,
        );
      }
    }
    setAdd((s) => (s ? { ...s, running: false } : s));
    await onSourcesChanged();
  }

  const totalJobsSelected = candidates
    ?.filter((c) => selected.has(c.token))
    .reduce((sum, c) => sum + c.job_count, 0) ?? 0;

  return (
    <details className="card p-4" open={candidates !== null || add !== null}>
      <summary className="cursor-pointer text-sm font-medium">
        Discover — search for new Greenhouse boards
      </summary>
      <div className="mt-4 space-y-4">
        <div className="flex gap-2 text-sm">
          <ModeTab active={mode === "search"} onClick={() => setMode("search")}>
            Auto-search (needs Anthropic key)
          </ModeTab>
          <ModeTab active={mode === "paste"} onClick={() => setMode("paste")}>
            Paste text
          </ModeTab>
        </div>

        {mode === "search" ? (
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='e.g. "climate energy startups" or "healthtech remote series A"'
              className="flex-1 rounded-lg border px-3 py-2 bg-transparent text-sm"
              style={{ borderColor: "var(--border)" }}
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === "Enter") runDiscover();
              }}
            />
            <button
              type="button"
              onClick={runDiscover}
              disabled={loading || !query.trim()}
              className="rounded-lg px-4 py-2 text-white font-medium text-sm whitespace-nowrap disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder={"Paste anything — Google results, articles, LinkedIn posts,\nyour own list. We'll pull out any boards.greenhouse.io/<token>\nURLs and validate them."}
              rows={6}
              disabled={loading}
              className="w-full rounded-lg border px-3 py-2 bg-transparent font-mono text-xs"
              style={{ borderColor: "var(--border)" }}
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={runDiscover}
                disabled={loading || !pasteText.trim()}
                className="rounded-lg px-4 py-2 text-white font-medium text-sm whitespace-nowrap disabled:opacity-50"
                style={{ background: "var(--accent)" }}
              >
                {loading ? "Validating…" : "Extract & validate"}
              </button>
            </div>
          </div>
        )}

        {error && (
          <p className="text-sm" style={{ color: "#dc2626" }}>
            {error}
          </p>
        )}

        {candidates && (
          <div className="space-y-3">
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              Found {totalSeen} unique tokens · filtered out {filteredOut} (404 or 0 jobs) · {candidates.length} live boards
            </p>
            {candidates.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--muted)" }}>
                No live boards found. Try a different query or paste more URLs.
              </p>
            ) : (
              <>
                <div className="rounded-lg border overflow-x-auto" style={{ borderColor: "var(--border)" }}>
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ background: "var(--bg)" }}>
                        <Th className="w-10">
                          <input
                            type="checkbox"
                            checked={selected.size === candidates.filter((c) => !c.already_registered).length && selected.size > 0}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelected(new Set(candidates.filter((c) => !c.already_registered).map((c) => c.token)));
                              } else {
                                setSelected(new Set());
                              }
                            }}
                          />
                        </Th>
                        <Th>Company</Th>
                        <Th>Jobs</Th>
                        <Th>Board</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((c) => (
                        <tr key={c.token} style={{ borderTop: "1px solid var(--border)" }}>
                          <Td>
                            <input
                              type="checkbox"
                              checked={selected.has(c.token)}
                              disabled={c.already_registered}
                              onChange={() => toggle(c.token)}
                            />
                          </Td>
                          <Td>
                            <span className={c.already_registered ? "opacity-60" : ""}>
                              {c.company_name}
                              {c.already_registered && (
                                <span
                                  className="ml-2 text-xs rounded-full px-2 py-0.5"
                                  style={{ background: "var(--bg)", color: "var(--muted)", border: "1px solid var(--border)" }}
                                >
                                  already added
                                </span>
                              )}
                            </span>
                          </Td>
                          <Td>{c.job_count}</Td>
                          <Td>
                            <a
                              href={c.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline text-xs"
                              style={{ color: "var(--accent)" }}
                            >
                              {c.token}
                            </a>
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <p className="text-sm" style={{ color: "var(--muted)" }}>
                    {selected.size} selected · {totalJobsSelected.toLocaleString()} jobs will be added
                  </p>
                  <button
                    type="button"
                    onClick={addSelected}
                    disabled={selected.size === 0 || add?.running}
                    className="rounded-lg px-4 py-2 text-white font-medium text-sm disabled:opacity-50"
                    style={{ background: "var(--accent)" }}
                  >
                    {add?.running
                      ? `Adding ${add.done}/${add.total}…`
                      : `Add ${selected.size} selected`}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {add && add.log.length > 0 && (
          <ul className="text-xs space-y-1 max-h-64 overflow-y-auto rounded border p-2" style={{ borderColor: "var(--border)" }}>
            {add.log.map((entry, i) => (
              <li
                key={i}
                style={{
                  color:
                    entry.result === "added"
                      ? "#16a34a"
                      : entry.result === "skipped"
                        ? "var(--muted)"
                        : "#dc2626",
                }}
              >
                [{entry.result}] {entry.token} — {entry.detail}
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg px-3 py-1.5 text-xs font-medium border"
      style={{
        borderColor: active ? "var(--accent)" : "var(--border)",
        background: active ? "var(--bg)" : "transparent",
        color: active ? "var(--accent)" : "var(--muted)",
      }}
    >
      {children}
    </button>
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
  return <td className={`px-3 py-2 ${className}`}>{children}</td>;
}
