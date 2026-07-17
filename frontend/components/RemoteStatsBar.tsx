import Link from "next/link";

import type { FacetValue } from "@/lib/api";

interface Props {
  values: FacetValue[];
  currentSearchParams: URLSearchParams;
}

const LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "Onsite",
  unknown: "Unknown",
};

const COLORS: Record<string, string> = {
  remote: "#16a34a",
  hybrid: "#eab308",
  onsite: "#64748b",
  unknown: "#cbd5e1",
};

const ORDER = ["remote", "hybrid", "unknown", "onsite"];

export function RemoteStatsBar({ values, currentSearchParams }: Props) {
  if (values.length === 0) return null;
  const total = values.reduce((s, v) => s + v.count, 0);
  if (total === 0) return null;
  const sorted = [...values].sort(
    (a, b) => (ORDER.indexOf(a.value) + 100) - (ORDER.indexOf(b.value) + 100),
  );

  function hrefFor(value: string): string {
    const next = new URLSearchParams(currentSearchParams.toString());
    if (next.get("remote_type") === value) next.delete("remote_type");
    else next.set("remote_type", value);
    const q = next.toString();
    return q ? `/?${q}` : "/";
  }

  const active = currentSearchParams.get("remote_type") ?? "";
  const activeSet = new Set(active.split(",").filter(Boolean));

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">Remote status breakdown</h2>
        <span className="text-xs" style={{ color: "var(--muted)" }}>
          {total.toLocaleString()} job{total === 1 ? "" : "s"} in current results
        </span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}>
        {sorted.map((v) => {
          const pct = (v.count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={v.value}
              title={`${LABELS[v.value] ?? v.value}: ${v.count} (${pct.toFixed(0)}%)`}
              style={{ width: `${pct}%`, background: COLORS[v.value] ?? "var(--muted)" }}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
        {sorted.map((v) => {
          const pct = (v.count / total) * 100;
          const isActive = activeSet.has(v.value);
          return (
            <Link
              key={v.value}
              href={hrefFor(v.value)}
              className="flex items-center gap-1.5 rounded px-1 py-0.5 -mx-1"
              style={{
                background: isActive ? "var(--bg)" : "transparent",
                border: `1px solid ${isActive ? "var(--accent)" : "transparent"}`,
                color: isActive ? "var(--accent)" : "inherit",
              }}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: COLORS[v.value] ?? "var(--muted)" }}
              />
              <span className="font-medium">{LABELS[v.value] ?? v.value}</span>
              <span style={{ color: "var(--muted)" }}>
                {v.count} ({pct.toFixed(0)}%)
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
