import json
from pathlib import Path

from app.providers.greenhouse.provider import GreenhouseProvider

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "greenhouse_jobs.json").read_text())


def test_normalize_maps_core_fields():
    provider = GreenhouseProvider()
    raw_job = FIXTURE["jobs"][0]

    normalized = provider.normalize(raw_job, company_name="Acme")

    assert normalized.source_provider == "greenhouse"
    assert normalized.source_job_id == "4000001"
    assert normalized.company_name == "Acme"
    assert normalized.title == "Senior Backend Engineer"
    assert normalized.canonical_url == "https://boards.greenhouse.io/acme/jobs/4000001"
    assert normalized.location == "Remote - United States"
    assert normalized.department == "Engineering"
    assert "Senior Backend Engineer" in normalized.description
    assert normalized.posted_at is not None
    assert normalized.posted_at.year == 2026


def test_normalize_handles_missing_department():
    provider = GreenhouseProvider()
    raw_job = dict(FIXTURE["jobs"][0])
    raw_job["departments"] = []

    normalized = provider.normalize(raw_job, company_name="Acme")

    assert normalized.department is None


def test_normalize_handles_missing_location():
    provider = GreenhouseProvider()
    raw_job = dict(FIXTURE["jobs"][0])
    raw_job["location"] = None

    normalized = provider.normalize(raw_job, company_name="Acme")

    assert normalized.location is None
