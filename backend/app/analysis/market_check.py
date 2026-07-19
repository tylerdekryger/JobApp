"""Per-job market-context lookup.

Ashby (and Greenhouse to a lesser extent) let posters bump ``publishedAt`` at will —
so a job showing "posted 1 day ago" in our table may in fact have been circulating
for months elsewhere. We can't fix that at the source, but we CAN cross-check LinkedIn
via Tavily: their snippets often carry age hints ("3 months ago", "4,000+ applicants",
"No longer accepting applications"), which is exactly the market context users need.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


class MarketCheckError(RuntimeError):
    pass


@dataclass
class MarketCheckResult:
    summary: str
    linkedin_url: str | None


def market_check(*, title: str, company: str) -> MarketCheckResult:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        raise MarketCheckError(
            "TAVILY_API_KEY is not set. Add it to your environment to enable market checks."
        )

    query = f'"{title}" "{company}" hiring'
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True,
                "include_domains": ["linkedin.com"],
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise MarketCheckError(f"Tavily request failed: {exc}") from exc

    if r.status_code != 200:
        try:
            msg = r.json().get("error") or r.json().get("detail") or r.text
        except ValueError:
            msg = r.text
        raise MarketCheckError(f"Tavily error {r.status_code}: {str(msg)[:200]}")

    data = r.json()
    answer = (data.get("answer") or "").strip()
    results = data.get("results") or []

    # Find the most likely LinkedIn job posting URL.
    linkedin_url: str | None = None
    for res in results:
        url = res.get("url") or ""
        if "/jobs/view/" in url:
            linkedin_url = url
            break
    if linkedin_url is None and results:
        # Fall back to the top result even if it's a person/profile — user can judge.
        linkedin_url = results[0].get("url")

    # Build a compact summary. Prefer Tavily's answer; append age/applicant hints from the
    # top snippets when we can spot them.
    snippets = "\n".join((r.get("content") or "")[:200] for r in results[:3])
    hints: list[str] = []
    lower = snippets.lower()
    for phrase in (
        "no longer accepting applications",
        "applicants",
        "months ago",
        "weeks ago",
        "days ago",
        "1 month ago",
    ):
        # Grab the surrounding ~40 chars so the hint has context.
        idx = lower.find(phrase)
        if idx == -1:
            continue
        left = max(0, idx - 20)
        right = min(len(snippets), idx + len(phrase) + 40)
        hints.append(snippets[left:right].strip())

    hint_text = " · ".join(dict.fromkeys(hints))  # de-dup while preserving order
    summary_parts = []
    if answer:
        summary_parts.append(answer)
    if hint_text:
        summary_parts.append(f"Signals: {hint_text}")
    if not summary_parts:
        summary_parts.append("No LinkedIn presence found for this exact title + company.")

    return MarketCheckResult(
        summary=" — ".join(summary_parts),
        linkedin_url=linkedin_url,
    )
