"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import type { FacetValue } from "@/lib/api";

interface FacetSectionProps {
  title: string;
  values: FacetValue[];
  paramKey: string;
  currentValue: string | null;
  emptyLabel: string;
}

function makeHref(
  current: URLSearchParams,
  paramKey: string,
  value: string | null,
): string {
  const next = new URLSearchParams(current.toString());
  if (value === null || next.get(paramKey) === value) {
    next.delete(paramKey);
  } else {
    next.set(paramKey, value);
  }
  const q = next.toString();
  return q ? `/?${q}` : "/";
}

function FacetSection({ title, values, paramKey, currentValue, emptyLabel }: FacetSectionProps) {
  const params = useSearchParams();
  if (values.length === 0) {
    return (
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--muted)" }}>
          {title}
        </h3>
        <p className="text-sm" style={{ color: "var(--muted)" }}>{emptyLabel}</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--muted)" }}>
        {title}
      </h3>
      <ul className="space-y-1">
        {values.map((v) => {
          const isActive = currentValue === v.value;
          return (
            <li key={v.value}>
              <Link
                href={makeHref(params, paramKey, isActive ? null : v.value)}
                className="flex items-center justify-between gap-2 text-sm rounded-md px-2 py-1 -mx-2 transition-colors"
                style={{
                  background: isActive ? "var(--bg)" : "transparent",
                  border: `1px solid ${isActive ? "var(--accent)" : "transparent"}`,
                  color: isActive ? "var(--accent)" : "inherit",
                }}
              >
                <span className="truncate" title={v.value}>{v.value}</span>
                <span className="flex-shrink-0 text-xs" style={{ color: "var(--muted)" }}>{v.count}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface Props {
  facets: {
    departments: FacetValue[];
    locations: FacetValue[];
    companies: FacetValue[];
  };
  activeLocation: string | null;
  activeCompanyId: string | null;
  companiesById: Record<string, string>;
}

export function FacetPanel({ facets, activeLocation, activeCompanyId, companiesById }: Props) {
  // For companies we filter on company_id, so we present them as name → click sets company_id.
  const params = useSearchParams();
  const companyNameToId: Record<string, string> = {};
  for (const [id, name] of Object.entries(companiesById)) {
    companyNameToId[name] = id;
  }
  return (
    <aside className="card p-4 space-y-5 sticky top-4">
      <div>
        <h2 className="text-sm font-semibold">Breakdown</h2>
        <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
          Top values in your current results. Click to filter.
        </p>
      </div>
      <FacetSection
        title="Locations"
        values={facets.locations}
        paramKey="location"
        currentValue={activeLocation}
        emptyLabel="No location data."
      />
      <FacetSection
        title="Departments"
        values={facets.departments}
        paramKey="department"
        currentValue={null}
        emptyLabel="No department data."
      />
      {facets.companies.length > 1 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--muted)" }}>
            Companies
          </h3>
          <ul className="space-y-1">
            {facets.companies.map((v) => {
              const cid = companyNameToId[v.value];
              if (!cid) return null;
              const isActive = activeCompanyId === cid;
              const next = new URLSearchParams(params.toString());
              if (isActive) next.delete("company_id");
              else next.set("company_id", cid);
              const q = next.toString();
              return (
                <li key={v.value}>
                  <Link
                    href={q ? `/?${q}` : "/"}
                    className="flex items-center justify-between gap-2 text-sm rounded-md px-2 py-1 -mx-2"
                    style={{
                      background: isActive ? "var(--bg)" : "transparent",
                      border: `1px solid ${isActive ? "var(--accent)" : "transparent"}`,
                      color: isActive ? "var(--accent)" : "inherit",
                    }}
                  >
                    <span className="truncate">{v.value}</span>
                    <span className="flex-shrink-0 text-xs" style={{ color: "var(--muted)" }}>{v.count}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </aside>
  );
}
