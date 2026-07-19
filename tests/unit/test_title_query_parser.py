"""Unit tests for the boolean AND/OR/parens title-query parser."""
from app.api.routes.jobs import _parse_title_tokens, _tokenize_title_query


def _render(node) -> str:
    """Cheap pretty-printer so assertions read like the source query."""
    kind = node[0]
    if kind == "term":
        return f"'{node[1]}'"
    if kind == "and":
        return "(" + " AND ".join(_render(c) for c in node[1]) + ")"
    if kind == "or":
        return "(" + " OR ".join(_render(c) for c in node[1]) + ")"
    raise AssertionError(kind)


def _parse(q: str):
    tokens = _tokenize_title_query(q)
    return _parse_title_tokens(tokens)


def test_single_term():
    assert _render(_parse("Manager")) == "'Manager'"


def test_multi_word_term_stays_together():
    assert _render(_parse("Customer Success")) == "'Customer Success'"


def test_or_two_terms():
    assert _render(_parse("Manager OR Analyst")) == "('Manager' OR 'Analyst')"


def test_comma_is_or_shorthand():
    assert _render(_parse("Manager, Customer Success")) == "('Manager' OR 'Customer Success')"


def test_and_binds_tighter_than_or():
    # From the earlier user example — standard precedence.
    got = _render(_parse("Customer Success AND Operation OR Analyst OR GTM"))
    assert got == "(('Customer Success' AND 'Operation') OR 'Analyst' OR 'GTM')"


def test_parens_override_precedence():
    # The reported bug: user wants Customer Success required across the OR list.
    got = _render(_parse("Customer Success AND (Manager OR Operation OR Analyst OR GTM OR Engineer)"))
    assert got == "('Customer Success' AND ('Manager' OR 'Operation' OR 'Analyst' OR 'GTM' OR 'Engineer'))"


def test_nested_parens():
    got = _render(_parse("(A OR B) AND (C OR D)"))
    assert got == "(('A' OR 'B') AND ('C' OR 'D'))"


def test_lowercase_and_or_stay_literal():
    assert _render(_parse("Research and Development")) == "'Research and Development'"


def test_unbalanced_close_paren_is_tolerated():
    # Ignore the stray close-paren rather than crashing.
    assert _render(_parse("Manager AND Analyst)")) == "('Manager' AND 'Analyst')"


def test_unbalanced_open_paren_is_tolerated():
    # A missing close-paren should still parse the rest of the expression.
    assert _render(_parse("Manager AND (Analyst OR GTM")) == "('Manager' AND ('Analyst' OR 'GTM'))"


def test_empty_returns_empty_tokens():
    assert _tokenize_title_query("") == []
    assert _tokenize_title_query("   ") == []
