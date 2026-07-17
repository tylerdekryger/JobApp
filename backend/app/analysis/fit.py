"""LLM-based fit/gap analysis of a job posting against the user's resume.

Uses Anthropic's Haiku model — cheap enough to run per-row on demand.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from anthropic import Anthropic, APIError

from app.normalization.text import strip_html

MODEL = "claude-haiku-4-5"
MAX_JOB_CHARS = 8000  # trim absurdly long JDs; still plenty of signal
MAX_RESUME_CHARS = 8000


class AnalysisConfigError(RuntimeError):
    """Raised when the API key is missing or the resume is empty."""


@dataclass
class JobAnalysis:
    fit: str
    gaps: str


def _client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise AnalysisConfigError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment (e.g. .env) to enable analysis."
        )
    return Anthropic(api_key=api_key)


def analyze_job_against_resume(
    *,
    resume_text: str,
    job_title: str,
    company_name: str,
    job_location: str | None,
    job_description_html: str,
) -> JobAnalysis:
    if not resume_text.strip():
        raise AnalysisConfigError("Resume is empty. Add it on the /profile page first.")

    resume = resume_text.strip()[:MAX_RESUME_CHARS]
    plain = strip_html(job_description_html).strip()[:MAX_JOB_CHARS]

    system = (
        "You help a job seeker evaluate individual roles against their resume. "
        "You return strict JSON with fields `fit` and `gaps`. Each field is 1-3 sentences, "
        "specific and concrete, mentioning skills/experience rather than platitudes. "
        "Never repeat the job title or company name. If the role is clearly a poor fit, "
        "say so in `fit` and be honest in `gaps`."
    )
    user = (
        f"# Resume\n{resume}\n\n"
        f"# Job\n"
        f"Title: {job_title}\n"
        f"Company: {company_name}\n"
        f"Location: {job_location or 'not specified'}\n\n"
        f"Description:\n{plain}\n\n"
        'Respond with JSON only, matching this schema exactly: '
        '{"fit": "...", "gaps": "..."}'
    )

    client = _client()
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except APIError as exc:
        raise AnalysisConfigError(f"Anthropic API error: {exc}") from exc

    raw = "".join(block.text for block in message.content if getattr(block, "type", "") == "text").strip()
    # Model often wraps JSON in ```json … ``` — be forgiving.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[len("json"):]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnalysisConfigError(f"Model returned non-JSON output: {raw[:300]}") from exc

    fit = str(parsed.get("fit", "")).strip()
    gaps = str(parsed.get("gaps", "")).strip()
    if not fit or not gaps:
        raise AnalysisConfigError(f"Model response missing fit/gaps: {parsed}")
    return JobAnalysis(fit=fit, gaps=gaps)
