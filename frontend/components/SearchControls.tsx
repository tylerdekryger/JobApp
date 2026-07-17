"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import type { CompanySummary } from "@/lib/api";

interface Props {
  companies: CompanySummary[];
}

export function SearchControls({ companies }: Props) {
  const router = useRouter();
  const params = useSearchParams();

  const [q, setQ] = useState(params.get("q") ?? "");
  const [location, setLocation] = useState(params.get("location") ?? "");
  const [companyId, setCompanyId] = useState(params.get("company_id") ?? "");
  const [postedSince, setPostedSince] = useState(params.get("posted_since_days") ?? "");
  // "Remote (include unknown)": true when the filter is anything that includes 'remote'
  const remoteParam = params.get("remote_type") ?? "";
  const [remoteEligible, setRemoteEligible] = useState(remoteParam.split(",").includes("remote"));

  useEffect(() => {
    setQ(params.get("q") ?? "");
    setLocation(params.get("location") ?? "");
    setCompanyId(params.get("company_id") ?? "");
    setPostedSince(params.get("posted_since_days") ?? "");
    const r = params.get("remote_type") ?? "";
    setRemoteEligible(r.split(",").includes("remote"));
  }, [params]);

  function applyFilters(overrides: Record<string, string> = {}) {
    // Preserve params we don't manage here (e.g. `department` set via facet click).
    const usp = new URLSearchParams(params.toString());
    const set = (key: string, value: string) => {
      const v = overrides[key] !== undefined ? overrides[key] : value;
      if (v) usp.set(key, v);
      else usp.delete(key);
    };
    set("q", q);
    set("location", location);
    set("company_id", companyId);
    set("posted_since_days", postedSince);
    // Preserve any explicit remote_type set via the facet panel (e.g. "onsite" alone).
    // Only overwrite it if the user directly toggled the "Remote (include unknown)" checkbox.
    if (overrides["remote_type"] !== undefined) {
      set("remote_type", overrides["remote_type"]);
    }
    const query = usp.toString();
    router.push(query ? `/?${query}` : "/");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    applyFilters();
  }

  function reset() {
    setQ("");
    setLocation("");
    setCompanyId("");
    setPostedSince("");
    setRemoteEligible(false);
    router.push("/");
  }

  return (
    <form onSubmit={handleSubmit} className="card p-4 space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search titles, descriptions, companies..."
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
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>
            Location
          </span>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Remote, New York, London"
            className="rounded-lg border px-3 py-2 bg-transparent"
            style={{ borderColor: "var(--border)" }}
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>
            Company
          </span>
          <select
            value={companyId}
            onChange={(e) => {
              setCompanyId(e.target.value);
              applyFilters({ company_id: e.target.value });
            }}
            className="rounded-lg border px-3 py-2 bg-transparent"
            style={{ borderColor: "var(--border)" }}
          >
            <option value="">All companies</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.active_job_count})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>
            Posted within
          </span>
          <select
            value={postedSince}
            onChange={(e) => {
              setPostedSince(e.target.value);
              applyFilters({ posted_since_days: e.target.value });
            }}
            className="rounded-lg border px-3 py-2 bg-transparent"
            style={{ borderColor: "var(--border)" }}
          >
            <option value="">Any time</option>
            <option value="1">Last 24 hours</option>
            <option value="3">Last 3 days</option>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
          </select>
        </label>
      </div>
      <div className="flex justify-between items-center gap-3 flex-wrap text-sm">
        <label className="flex items-center gap-2 select-none cursor-pointer">
          <input
            type="checkbox"
            checked={remoteEligible}
            onChange={(e) => {
              setRemoteEligible(e.target.checked);
              applyFilters({ remote_type: e.target.checked ? "remote,unknown" : "" });
            }}
            className="h-4 w-4"
          />
          <span className="font-medium">Remote (include unknown)</span>
          <span style={{ color: "var(--muted)" }}>
            confirmed remote + jobs where remote status isn&apos;t stated
          </span>
        </label>
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
