"""Unit tests for the boolean AND/OR title-query parser on JobFilters."""
from app.api.routes.jobs import JobFilters


def _parse(q: str | None) -> list[list[str]]:
    f = JobFilters(
        q=None, location=None, department=None, remote_type=None,
        title_contains=q, company_id=None, source_id=None, status=None,
        posted_since_days=None,
    )
    return f._title_or_groups()


def test_empty_and_none():
    assert _parse(None) == []
    assert _parse("") == []
    assert _parse("   ") == []


def test_single_term():
    assert _parse("Manager") == [["Manager"]]


def test_multi_word_term_stays_together():
    assert _parse("Customer Success") == [["Customer Success"]]


def test_comma_is_or_shorthand():
    # Backward-compat with the previous comma-only syntax.
    assert _parse("Manager, Customer Success") == [["Manager"], ["Customer Success"]]


def test_explicit_or():
    assert _parse("Manager OR Customer Success") == [["Manager"], ["Customer Success"]]


def test_and_binds_tighter_than_or():
    # From the user's example.
    assert _parse("Customer Success AND Operation OR Analyst OR GTM") == [
        ["Customer Success", "Operation"],
        ["Analyst"],
        ["GTM"],
    ]


def test_mixed_comma_and_boolean():
    assert _parse("Manager AND Sales, Analyst") == [
        ["Manager", "Sales"],
        ["Analyst"],
    ]


def test_lowercase_and_or_are_literal():
    # Only UPPERCASE AND/OR are operators; "and" in "Research and Development" is literal.
    assert _parse("Research and Development") == [["Research and Development"]]
    assert _parse("Sales or Marketing") == [["Sales or Marketing"]]


def test_extra_whitespace_is_tolerated():
    assert _parse("  Manager   AND   Sales  ") == [["Manager", "Sales"]]
