"""Text normalization helpers used at job-normalize time and at boilerplate detection time.

Kept deliberately simple. Everything here is heuristic — the goal is "usually right on real ATS
postings", not perfect NLP. When in doubt, prefer returning `None` / `"unknown"` over guessing.
"""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser

_LEADING_ID_RE = re.compile(r"^\s*\d[\d\-_.]*\s+")

_REMOTE_LOCATION_TOKENS = (
    "remote",
    "anywhere",
    "distributed",
    "work from home",
    "wfh",
    "virtual",
)
_HYBRID_LOCATION_TOKENS = ("hybrid", "flex office", "flexible office")

_REMOTE_BODY_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfully\s+remote\b",
        r"\bremote[- ](first|only|friendly)\b",
        r"\b100%\s*remote\b",
        r"\bremote\s+(position|role|opportunity)\b",
        r"\bwork\s+from\s+(home|anywhere)\b",
        r"\bwork\s+remotely\b",
        r"\banywhere\s+in\s+the\s+(us|u\.s\.|united\s+states|world|country)\b",
        r"\bthis\s+(is|role\s+is)\s+(a\s+)?remote\b",
        r"\bposition\s+is\s+(fully\s+)?remote\b",
    )
)

_HYBRID_BODY_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhybrid\s+(role|position|work|schedule|environment|model)\b",
        r"\bin\s+the\s+office\s+\d+\s+days?\b",
        r"\b\d+\s+days?\s+(a|per)\s+week\s+in\s+(the\s+)?office\b",
    )
)

_ONSITE_NEGATIONS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bnot\s+(a\s+)?remote\b",
        r"\bno\s+remote\b",
        r"\bmust\s+be\s+(located|based)\s+in\b",
        r"\bin[- ]person\s+role\b",
        r"\bon[- ]site\s+(only|role|required)\b",
    )
)


class _HTMLTextExtractor(HTMLParser):
    """Extract visible text from an HTML fragment, collapsing whitespace."""

    def __init__(self) -> None:
        super().__init__()
        self._buf: list[str] = []

    def handle_data(self, data: str) -> None:
        self._buf.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._buf)).strip()


def strip_html(html: str) -> str:
    if not html:
        return ""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        # Fall back to a naive tag strip; malformed HTML shouldn't crash normalization.
        return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html)).strip()
    return parser.text()


def clean_department(department: str | None) -> str | None:
    """Strip Greenhouse's internal numeric department IDs (e.g. '1150 Solutions Architecture')."""
    if department is None:
        return None
    cleaned = _LEADING_ID_RE.sub("", department).strip()
    return cleaned or None


def detect_remote_type(location: str | None, description_html: str | None) -> str:
    """Return one of 'remote', 'hybrid', 'onsite', 'unknown'.

    Location text wins over body text when it's explicit. Body text is used as a fallback and
    to promote e.g. an office-based location to 'hybrid' when the description says so.
    """
    loc = (location or "").lower()
    body = strip_html(description_html or "")

    if loc:
        if any(token in loc for token in _HYBRID_LOCATION_TOKENS):
            return "hybrid"
        if any(token in loc for token in _REMOTE_LOCATION_TOKENS):
            return "remote"

    if any(p.search(body) for p in _ONSITE_NEGATIONS):
        # Body explicitly rules out remote — prefer whatever the location said, or onsite.
        return "hybrid" if any(p.search(body) for p in _HYBRID_BODY_PATTERNS) else "onsite"

    if any(p.search(body) for p in _REMOTE_BODY_PATTERNS):
        return "remote"

    if any(p.search(body) for p in _HYBRID_BODY_PATTERNS):
        return "hybrid"

    if loc and loc.strip().lower() not in ("", "n/a", "not specified", "unknown"):
        return "onsite"
    return "unknown"


_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?\s+")
_CLOSING_BLOCK_TAGS = ("</p>", "</h1>", "</h2>", "</h3>", "</h4>", "</ul>", "</ol>", "</li>", "</div>")


def _snap_to_natural_boundary(prefix: str) -> str:
    """Trim a raw common prefix back to the last natural boundary so we don't strip mid-sentence."""
    for tag in _CLOSING_BLOCK_TAGS:
        idx = prefix.rfind(tag)
        if idx > 0:
            return prefix[: idx + len(tag)]
    matches = list(_SENTENCE_END_RE.finditer(prefix))
    if matches:
        end = matches[-1].end()
        return prefix[:end]
    return ""  # Nothing safe to snap to.


def longest_common_prefix(texts: list[str]) -> str:
    """Strict longest common prefix — every text must agree at every position."""
    if not texts:
        return ""
    prefix = texts[0]
    for other in texts[1:]:
        limit = min(len(prefix), len(other))
        i = 0
        while i < limit and prefix[i] == other[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            return ""
    return prefix


def consensus_prefix(texts: list[str], *, min_agreement: float = 0.25) -> str:
    """Find the longest prefix shared by the dominant template across `texts`.

    At each character position we pick the mode character among the surviving descriptions and
    drop the ones that don't match. We stop when the surviving set drops below `min_agreement`
    of the original count. This lets us find the majority template even when a source uses
    several template variants (e.g. Stripe's mix of ``<h2>``/``<h3>`` openings) that would
    break strict LCP or position-independent voting.

    The returned string is a real prefix of at least one input, so ``strip_boilerplate`` can
    remove it verbatim from any conforming description.
    """
    if not texts:
        return ""
    original_count = len(texts)
    min_survivors = max(1, int(min_agreement * original_count))
    survivors = list(texts)
    prefix: list[str] = []
    max_len = max(len(t) for t in survivors)
    for i in range(max_len):
        chars_at_i = [t[i] for t in survivors if i < len(t)]
        if not chars_at_i:
            break
        mode_char, _ = Counter(chars_at_i).most_common(1)[0]
        next_survivors = [t for t in survivors if i < len(t) and t[i] == mode_char]
        if len(next_survivors) < min_survivors:
            break
        survivors = next_survivors
        prefix.append(mode_char)
    return "".join(prefix)


def detect_boilerplate_prefix(descriptions: list[str], *, min_chars: int = 120, min_samples: int = 3) -> str:
    """Return the shared boilerplate prefix across `descriptions`, or '' if none is significant.

    Requires at least `min_samples` samples and a snap-safe prefix of at least `min_chars`. Meant
    to be called after a sync when we have all descriptions from a given source in hand.
    """
    if len(descriptions) < min_samples:
        return ""
    raw = consensus_prefix(descriptions)
    if len(raw) < min_chars:
        return ""
    snapped = _snap_to_natural_boundary(raw)
    if len(snapped) < min_chars:
        return ""
    return snapped


def strip_boilerplate(description: str, prefix: str) -> str:
    if not prefix or not description:
        return description
    if description.startswith(prefix):
        return description[len(prefix) :].lstrip()
    return description
