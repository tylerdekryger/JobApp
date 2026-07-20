"""Build and send the daily digest email.

For each active DigestPreset, find jobs added in the last 24h that match the preset's
title query AND pass the standard remote-eligible + US + 30-day filters. Format them
as an HTML email and send via Gmail SMTP.
"""
from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.routes.jobs import JobFilters, _us_eligibility_condition
from app.db import SessionLocal
from app.domain.models import Company, DigestPreset, Job

logger = logging.getLogger(__name__)

DIGEST_LOOKBACK = timedelta(hours=24)
MAX_ROWS_PER_PRESET = 40  # keep email readable


class DigestError(RuntimeError):
    """Raised on config or delivery failure — surfaced through the run-now endpoint."""


@dataclass
class PresetResult:
    preset: DigestPreset
    jobs: list[Job]


def _smtp_config() -> dict[str, str]:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    to_addr = os.getenv("DIGEST_TO_EMAIL", user).strip()
    if not user or not password:
        raise DigestError(
            "SMTP_USER and SMTP_PASSWORD are not set. Add them to your .env "
            "(use a Gmail App Password, not your login password) to enable the digest."
        )
    if not to_addr:
        raise DigestError("DIGEST_TO_EMAIL (or SMTP_USER) must be set.")
    return {"host": host, "port": str(port), "user": user, "password": password, "to": to_addr}


def _find_matching_jobs(session: Session, preset: DigestPreset, since: datetime) -> list[Job]:
    """Jobs first-seen OR reopened since `since`, matching the preset's title query,
    passing the standard remote-eligible + US + 30-day filters. Ordered newest first."""
    filters = JobFilters(
        q=None, location=None, department=None,
        remote_type="remote,unknown",
        title_contains=preset.title_contains or "",
        company_id=None, source_id=None, status="active",
        posted_since_days=None,
    )
    conditions = filters.build_conditions()

    # "New in the last 24h" — either freshly seen OR just reopened.
    seen_col = func.coalesce(Job.reopened_at, Job.first_seen_at)
    freshness = seen_col >= since

    # 30-day age filter (matches the search page).
    age_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    age = or_(Job.posted_at.is_(None), Job.posted_at >= age_cutoff)

    # US-only.
    us = _us_eligibility_condition()

    from sqlalchemy import select
    stmt = (
        select(Job)
        .join(Company, Company.id == Job.company_id)
        .options(joinedload(Job.company), joinedload(Job.job_source))
        .where(and_(freshness, age, us, *conditions))
        .order_by(seen_col.desc(), Job.posted_at.desc().nulls_last())
        .limit(MAX_ROWS_PER_PRESET)
    )
    return session.scalars(stmt).unique().all()


def _format_comp(job: Job) -> str:
    lo, hi, cur = job.salary_min, job.salary_max, (job.salary_currency or "USD").upper()
    if lo is None and hi is None:
        return ""
    sym = "$" if cur == "USD" else ""
    suffix = "" if sym else f" {cur}"

    def k(n: float) -> str:
        return f"{sym}{round(n / 1000)}K" if n >= 1000 else f"{sym}{round(n)}"

    if lo is not None and hi is not None and lo != hi:
        return f"{k(lo)}–{k(hi)}{suffix}"
    return f"{k(lo if lo is not None else hi)}{suffix}"


def _render_html(results: list[PresetResult]) -> str:
    parts: list[str] = [
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#0f172a;max-width:720px">',
        '<h2 style="margin:0 0 4px 0">Job digest — new matches in the last 24h</h2>',
        f'<p style="color:#64748b;margin:0 0 24px 0">Generated {datetime.now().strftime("%A, %B %-d, %I:%M %p")}</p>',
    ]
    total = sum(len(r.jobs) for r in results)
    if total == 0:
        parts.append('<p>No new matches in any of your presets today.</p>')
    for r in results:
        parts.append(f'<h3 style="margin:24px 0 4px 0">{escape(r.preset.name)}</h3>')
        parts.append(
            f'<p style="color:#64748b;margin:0 0 8px 0;font-size:13px">'
            f'Query: <code>{escape(r.preset.title_contains)}</code> · {len(r.jobs)} match{"" if len(r.jobs)==1 else "es"}</p>'
        )
        if not r.jobs:
            parts.append('<p style="color:#64748b;margin:0 0 8px 0">No new matches.</p>')
            continue
        parts.append('<table cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:14px">')
        parts.append(
            '<tr style="background:#f1f5f9;text-align:left">'
            '<th>Company</th><th>Role</th><th>Location</th><th>Comp</th><th></th></tr>'
        )
        for j in r.jobs:
            company = escape(j.company.name if j.company else "—")
            title = escape(j.title or "")
            loc = escape(j.location or "—")
            comp = escape(_format_comp(j))
            url = escape(j.canonical_url or "")
            parts.append(
                '<tr style="border-top:1px solid #e2e8f0">'
                f'<td>{company}</td>'
                f'<td><strong>{title}</strong></td>'
                f'<td>{loc}</td>'
                f'<td>{comp}</td>'
                f'<td><a href="{url}" style="color:#2563eb">Apply ↗</a></td>'
                '</tr>'
            )
        parts.append('</table>')
    parts.append('</div>')
    return "\n".join(parts)


def _render_text(results: list[PresetResult]) -> str:
    lines: list[str] = ["Job digest — new matches in the last 24h", ""]
    total = sum(len(r.jobs) for r in results)
    if total == 0:
        lines.append("No new matches in any of your presets today.")
    for r in results:
        lines.append("")
        lines.append(f"=== {r.preset.name} ===  ({len(r.jobs)} matches)")
        lines.append(f"Query: {r.preset.title_contains}")
        if not r.jobs:
            lines.append("  (no new matches)")
            continue
        for j in r.jobs:
            company = j.company.name if j.company else "—"
            comp = _format_comp(j) or ""
            comp_str = f" · {comp}" if comp else ""
            lines.append(f"  • {company} — {j.title} · {j.location or '—'}{comp_str}")
            lines.append(f"    {j.canonical_url}")
    return "\n".join(lines)


def _send(smtp: dict[str, str], subject: str, html: str, text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp["user"]
    msg["To"] = smtp["to"]
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=30) as s:
            s.starttls()
            s.login(smtp["user"], smtp["password"])
            s.sendmail(smtp["user"], [smtp["to"]], msg.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise DigestError(f"SMTP send failed: {exc}") from exc


@dataclass
class DigestSendResult:
    presets_run: int
    total_matches: int
    to: str
    subject: str
    skipped: str | None = None


def send_daily_digest(*, dry_run: bool = False) -> DigestSendResult:
    """Build the digest for all active presets and (unless dry_run) send it.

    Returns counts + destination so the on-demand endpoint can echo them back.
    Raises DigestError on config or SMTP problems.
    """
    from sqlalchemy import select
    session = SessionLocal()
    try:
        presets = list(session.scalars(
            select(DigestPreset).where(DigestPreset.is_active == True).order_by(DigestPreset.id)  # noqa: E712
        ))
        if not presets:
            return DigestSendResult(
                presets_run=0, total_matches=0, to="", subject="",
                skipped="No active presets. Add one on the /digest page.",
            )
        since = datetime.now(timezone.utc) - DIGEST_LOOKBACK
        results = [PresetResult(preset=p, jobs=_find_matching_jobs(session, p, since)) for p in presets]
        total_matches = sum(len(r.jobs) for r in results)
        html = _render_html(results)
        text = _render_text(results)
        subject = f"Job digest — {total_matches} new match{'' if total_matches == 1 else 'es'}"

        smtp = _smtp_config()
        if dry_run:
            return DigestSendResult(
                presets_run=len(presets), total_matches=total_matches, to=smtp["to"],
                subject=subject, skipped="dry_run",
            )
        _send(smtp, subject, html, text)

        now = datetime.now(timezone.utc)
        for p in presets:
            p.last_sent_at = now
        session.commit()

        logger.info(
            "daily digest sent to=%s presets=%d total_matches=%d",
            smtp["to"], len(presets), total_matches,
        )
        return DigestSendResult(
            presets_run=len(presets), total_matches=total_matches, to=smtp["to"], subject=subject,
        )
    finally:
        session.close()
