from app.normalization.text import (
    clean_department,
    consensus_prefix,
    detect_boilerplate_prefix,
    detect_remote_type,
    longest_common_prefix,
    strip_boilerplate,
    strip_html,
)


class TestCleanDepartment:
    def test_strips_leading_numeric_id(self):
        assert clean_department("1150 Solutions Architecture") == "Solutions Architecture"

    def test_strips_prefixed_ids_with_punctuation(self):
        assert clean_department("2317.1 Marketing - PMM") == "Marketing - PMM"

    def test_leaves_clean_names_alone(self):
        assert clean_department("Customer Success") == "Customer Success"

    def test_returns_none_for_none(self):
        assert clean_department(None) is None

    def test_returns_none_for_all_numeric(self):
        assert clean_department("1234 ") is None


class TestDetectRemoteType:
    def test_location_remote(self):
        assert detect_remote_type("Remote", "") == "remote"

    def test_location_remote_regional(self):
        assert detect_remote_type("Remote - United States", "") == "remote"

    def test_location_hybrid(self):
        assert detect_remote_type("Hybrid - New York", "") == "hybrid"

    def test_location_onsite(self):
        assert detect_remote_type("San Francisco, CA", "<p>Standard role.</p>") == "onsite"

    def test_body_promotes_to_remote(self):
        assert detect_remote_type("Anywhere in North America", None) == "remote"

    def test_body_fully_remote(self):
        assert detect_remote_type("New York, NY", "<p>This is a fully remote position.</p>") == "remote"

    def test_body_hybrid(self):
        assert detect_remote_type("New York, NY", "<p>Hybrid schedule, 3 days in office.</p>") == "hybrid"

    def test_negation_blocks_remote(self):
        assert detect_remote_type("New York, NY", "<p>This is not a remote role. In-office role.</p>") == "onsite"

    def test_unknown_when_no_location_and_no_signals(self):
        assert detect_remote_type(None, "<p>Generic description.</p>") == "unknown"

    def test_na_location_is_unknown(self):
        assert detect_remote_type("N/A", "") == "unknown"


class TestStripHtml:
    def test_strips_tags_and_collapses_whitespace(self):
        html = "<p>Hello   <strong>world</strong>.</p>\n<p>Second.</p>"
        assert strip_html(html) == "Hello world. Second."

    def test_handles_malformed_html(self):
        html = "<p>unclosed <div>tag</p>"
        assert "unclosed" in strip_html(html)


class TestBoilerplateDetection:
    def test_longest_common_prefix(self):
        texts = [
            "About us. We are Acme. Role: engineer.",
            "About us. We are Acme. Role: manager.",
            "About us. We are Acme. Role: designer.",
        ]
        assert longest_common_prefix(texts) == "About us. We are Acme. Role: "

    def test_consensus_prefix_tolerates_minority_variants(self):
        # 3 out of 4 texts share a long opening; one is a different template. Consensus should
        # still recover most of the majority prefix that strict LCP would miss.
        texts = [
            "About Acme. Acme is great. Different specifics per role for job A.",
            "About Acme. Acme is great. Different specifics per role for job B.",
            "About Acme. Acme is great. Different specifics per role for job C.",
            "Totally different opening for this outlier posting.",
        ]
        prefix = consensus_prefix(texts, min_agreement=0.7)
        assert prefix.startswith("About Acme. Acme is great.")
        # Strict LCP would break at 'T' vs 'A' (position 0); consensus should get much further.
        assert len(prefix) > 25
        assert longest_common_prefix(texts) == ""

    def test_consensus_prefix_stops_at_variation(self):
        texts = [
            "abcXXX",
            "abcYYY",
            "abcZZZ",
        ]
        # All agree on 'abc', diverge at position 3.
        assert consensus_prefix(texts, min_agreement=1.0) == "abc"

    def test_detects_boilerplate_when_significant(self):
        opening = "<p>Who we are. About Acme. Acme is a great company doing great things and growing fast.</p>"
        descriptions = [
            opening + "<p>Role A specifics.</p>",
            opening + "<p>Role B specifics.</p>",
            opening + "<p>Role C specifics.</p>",
        ]
        detected = detect_boilerplate_prefix(descriptions, min_chars=50, min_samples=3)
        # Should include the whole shared opening. May include a small amount past the </p>
        # depending on suffix similarity — that's fine as long as the boilerplate is captured.
        assert opening in detected
        assert detected.endswith("</p>")

    def test_no_boilerplate_when_too_short(self):
        descriptions = ["<p>hi</p>foo", "<p>hi</p>bar", "<p>hi</p>baz"]
        assert detect_boilerplate_prefix(descriptions, min_chars=50, min_samples=3) == ""

    def test_no_boilerplate_when_too_few_samples(self):
        descriptions = ["<p>same opening.</p>role1", "<p>same opening.</p>role2"]
        assert detect_boilerplate_prefix(descriptions, min_samples=3) == ""

    def test_snaps_to_closing_tag(self):
        # Common prefix here goes into the middle of "unique" — should snap back to </p>.
        descriptions = [
            "<p>Boilerplate paragraph one long enough to matter here.</p><p>uniqueA-different-tail</p>",
            "<p>Boilerplate paragraph one long enough to matter here.</p><p>uniqueB-quite-other-end</p>",
            "<p>Boilerplate paragraph one long enough to matter here.</p><p>uniqueC-completely-else</p>",
        ]
        detected = detect_boilerplate_prefix(descriptions, min_chars=40, min_samples=3)
        assert detected.endswith("</p>")
        # After the first </p>, the openings all read '<p>unique' — those 9 chars agree but the
        # snap-back should trim to the first </p> since nothing past it is common enough.
        assert "unique" not in detected or detected.count("unique") <= 1

    def test_strip_boilerplate_removes_prefix(self):
        prefix = "<p>Boilerplate.</p>"
        assert strip_boilerplate(prefix + "<p>real</p>", prefix) == "<p>real</p>"

    def test_strip_boilerplate_leaves_alone_when_prefix_missing(self):
        assert strip_boilerplate("<p>real</p>", "<p>Different.</p>") == "<p>real</p>"
