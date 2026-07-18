"""LLM-based fit/gap analysis of a job posting against the user's resume.

Prefers Google's Gemini (free tier, no card required); falls back to Anthropic Claude
if only an ANTHROPIC_API_KEY is set. Cheap enough either way to run per-row on demand.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx

from app.normalization.text import strip_html

GEMINI_MODEL = "gemini-flash-latest"
ANTHROPIC_MODEL = "claude-haiku-4-5"
MAX_JOB_CHARS = 8000
MAX_RESUME_CHARS = 8000


class AnalysisConfigError(RuntimeError):
    """Raised when no LLM provider is usable, or the input is invalid."""


@dataclass
class JobAnalysis:
    fit: str
    gaps: str


def _pick_provider() -> str:
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    raise AnalysisConfigError(
        "No LLM API key configured. Set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY."
    )


def _build_prompt(resume: str, title: str, company: str, location: str | None, plain: str) -> tuple[str, str]:
    system = (
        "You help a job seeker evaluate individual roles against their resume. "
        "Return strict JSON with fields `fit` and `gaps`. Each field is 1-3 sentences, "
        "specific and concrete, mentioning skills/experience rather than platitudes. "
        "Never repeat the job title or company name. If the role is clearly a poor fit, "
        "say so in `fit` and be honest in `gaps`."
    )
    user = (
        f"# Resume\n{resume}\n\n"
        f"# Job\n"
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location or 'not specified'}\n\n"
        f"Description:\n{plain}\n\n"
        'Respond with JSON only, matching this schema exactly: '
        '{"fit": "...", "gaps": "..."}'
    )
    return system, user


def _call_gemini(system: str, user: str) -> dict:
    key = os.environ["GEMINI_API_KEY"]
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"X-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "fit": {"type": "string"},
                        "gaps": {"type": "string"},
                    },
                    "required": ["fit", "gaps"],
                },
                "temperature": 0.2,
                "max_output_tokens": 2000,
            },
        },
        timeout=60,
    )
    if r.status_code != 200:
        # Surface the API's actual message so quota/auth errors are actionable in the UI.
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise AnalysisConfigError(f"Gemini API error ({r.status_code}): {msg[:300]}")
    body = r.json()
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise AnalysisConfigError(f"Gemini returned no text: {json.dumps(body)[:300]}")
    return json.loads(text)


def _call_anthropic(system: str, user: str) -> dict:
    from anthropic import Anthropic, APIError  # lazy import; SDK is optional at runtime

    client = Anthropic()
    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except APIError as exc:
        raise AnalysisConfigError(f"Anthropic API error: {exc}") from exc

    raw = "".join(block.text for block in message.content if getattr(block, "type", "") == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[len("json"):]
        raw = raw.strip()
    return json.loads(raw)


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

    provider = _pick_provider()  # raises AnalysisConfigError if nothing configured
    resume = resume_text.strip()[:MAX_RESUME_CHARS]
    plain = strip_html(job_description_html).strip()[:MAX_JOB_CHARS]
    system, user = _build_prompt(resume, job_title, company_name, job_location, plain)

    try:
        parsed = _call_gemini(system, user) if provider == "gemini" else _call_anthropic(system, user)
    except json.JSONDecodeError as exc:
        # Include a slice of the offending output so UI surfaces something diagnosable.
        raw = getattr(exc, "doc", "")
        raise AnalysisConfigError(
            f"{provider} returned non-JSON output: {raw[:200] if raw else 'empty'}"
        ) from exc

    fit = str(parsed.get("fit", "")).strip()
    gaps = str(parsed.get("gaps", "")).strip()
    if not fit or not gaps:
        raise AnalysisConfigError(f"Model response missing fit/gaps: {parsed}")
    return JobAnalysis(fit=fit, gaps=gaps)
