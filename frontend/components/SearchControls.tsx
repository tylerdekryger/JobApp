"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import type { CompanySummary } from "@/lib/api";

// Kept for signature parity with existing callers; not currently rendered — companies
// are visible directly in the results table.
interface Props {
  companies?: CompanySummary[];
}

export function SearchControls({}: Props) {
  const router = useRouter();
  const params = useSearchParams();

  const [q, setQ] = useState(params.get("q") ?? "");
  const [titleContains, setTitleContains] = useState(params.get("title_contains") ?? "");

  useEffect(() => {
    setQ(params.get("q") ?? "");
    setTitleContains(params.get("title_contains") ?? "");
  }, [params]);

  function apply() {
    const usp = new URLSearchParams(params.toString());
    const set = (key: string, value: string) => {
      if (value) usp.set(key, value);
      else usp.delete(key);
    };
    set("q", q);
    set("title_contains", titleContains);
    // Reset pagination when filters change.
    usp.delete("offset");
    const query = usp.toString();
    router.push(query ? `/?${query}` : "/");
  }

  function reset() {
    setQ("");
    setTitleContains("");
    router.push("/");
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        apply();
      }}
      className="card p-4 space-y-3 sticky top-0 z-20 shadow-sm"
    >
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search titles..."
          className="flex-1 rounded-lg border px-3 py-2 bg-transparent"
          style={{ borderColor: "var(--border)" }}
        />
        <button
          type="submit"
          className="rounded-lg px-4 py-2 text-white font-medium transition-colors"
          style={{ background: "var(--accent)" }}
        >
          Search
        </button>
      </div>
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>
          Role keywords <span className="font-normal">(comma-separated — title matches ANY)</span>
        </span>
        <input
          type="text"
          value={titleContains}
          onChange={(e) => setTitleContains(e.target.value)}
          placeholder="e.g. Manager, Customer Success, Solutions"
          className="rounded-lg border px-3 py-2 bg-transparent"
          style={{ borderColor: "var(--border)" }}
        />
      </label>
      <div className="flex justify-between items-center gap-3 flex-wrap text-sm">
        <span style={{ color: "var(--muted)" }}>
          Only remote-eligible roles posted in the last 30 days are shown.
        </span>
        <button
          type="button"
          onClick={reset}
          className="underline"
          style={{ color: "var(--accent)" }}
        >
          Reset
        </button>
      </div>
    </form>
  );
}
