from app.normalization.content_hash import compute_content_hash
from app.providers.base import NormalizedJob


def _job(**overrides) -> NormalizedJob:
    defaults = dict(
        source_provider="greenhouse",
        source_job_id="1",
        company_name="Acme",
        title="Engineer",
        description="Build things.",
        canonical_url="https://boards.greenhouse.io/acme/jobs/1",
        location="Remote",
    )
    defaults.update(overrides)
    return NormalizedJob(**defaults)


def test_same_content_produces_same_hash():
    assert compute_content_hash(_job()) == compute_content_hash(_job())


def test_changed_description_changes_hash():
    original = compute_content_hash(_job())
    changed = compute_content_hash(_job(description="Build different things."))
    assert original != changed


def test_changed_location_changes_hash():
    original = compute_content_hash(_job())
    changed = compute_content_hash(_job(location="Onsite"))
    assert original != changed


def test_unrelated_field_does_not_affect_hash():
    original = compute_content_hash(_job())
    same = compute_content_hash(_job(canonical_url="https://boards.greenhouse.io/acme/jobs/999"))
    assert original == same
