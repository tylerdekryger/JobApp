"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

interface Props {
  total: number;
  limit: number;
  offset: number;
}

export function Pagination({ total, limit, offset }: Props) {
  const params = useSearchParams();
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  function hrefFor(newOffset: number): string {
    const usp = new URLSearchParams(params.toString());
    if (newOffset === 0) usp.delete("offset");
    else usp.set("offset", String(newOffset));
    const q = usp.toString();
    return q ? `/?${q}` : "/";
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const prevDisabled = offset === 0;
  const nextDisabled = offset + limit >= total;

  return (
    <div className="flex items-center justify-between gap-3 flex-wrap text-sm">
      <p style={{ color: "var(--muted)" }}>
        Showing <strong>{from.toLocaleString()}–{to.toLocaleString()}</strong> of{" "}
        <strong>{total.toLocaleString()}</strong> · Page {currentPage} of {totalPages}
      </p>
      <div className="flex gap-2">
        <PageButton disabled={prevDisabled} href={hrefFor(Math.max(0, offset - limit))} label="← Prev" />
        <PageButton disabled={nextDisabled} href={hrefFor(offset + limit)} label="Next →" />
      </div>
    </div>
  );
}

function PageButton({ disabled, href, label }: { disabled: boolean; href: string; label: string }) {
  if (disabled) {
    return (
      <span
        className="rounded-lg px-3 py-1.5 text-sm border opacity-40"
        style={{ borderColor: "var(--border)", color: "var(--muted)" }}
      >
        {label}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className="rounded-lg px-3 py-1.5 text-sm border hover:opacity-90"
      style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
    >
      {label}
    </Link>
  );
}
