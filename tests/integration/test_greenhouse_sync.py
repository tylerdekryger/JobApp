import copy
import json
from pathlib import Path

import httpx
import respx
from sqlalchemy import select

from app.domain.models import Company, Job, JobSource
from app.sync.sync_service import sync_source

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "greenhouse_jobs.json").read_text())
BOARD_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"


def _make_source(db_session) -> JobSource:
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()

    source = JobSource(
        company_id=company.id,
        provider="greenhouse",
        source_url="https://boards.greenhouse.io/acme",
        source_identifier="acme",
        status="pending",
    )
    db_session.add(source)
    db_session.commit()
    return source


def _jobs_by_external_id(db_session, source_id: int) -> dict[str, Job]:
    jobs = db_session.scalars(select(Job).where(Job.job_source_id == source_id)).all()
    return {job.external_job_id: job for job in jobs}


def test_sync_adds_updates_and_closes_jobs(db_session):
    source = _make_source(db_session)

    first_payload = copy.deepcopy(FIXTURE)
    with respx.mock:
        respx.get(BOARD_JOBS_URL).mock(return_value=httpx.Response(200, json=first_payload))
        result = sync_source(db_session, source.id)

    assert result.jobs_found == 3
    assert result.jobs_added == 3
    assert result.jobs_updated == 0
    assert result.jobs_removed == 0

    jobs = _jobs_by_external_id(db_session, source.id)
    assert set(jobs) == {"4000001", "4000002", "4000003"}
    assert all(job.status == "active" for job in jobs.values())

    original_hash = jobs["4000001"].content_hash
    original_change_at = jobs["4000001"].last_content_change_at

    second_payload = copy.deepcopy(FIXTURE)
    second_payload["jobs"] = [job for job in second_payload["jobs"] if job["id"] != 4000003]
    for job in second_payload["jobs"]:
        if job["id"] == 4000001:
            job["content"] = "<p>Updated: we are now hiring a Staff Backend Engineer.</p>"

    with respx.mock:
        respx.get(BOARD_JOBS_URL).mock(return_value=httpx.Response(200, json=second_payload))
        result = sync_source(db_session, source.id)

    assert result.jobs_found == 2
    assert result.jobs_added == 0
    assert result.jobs_updated == 1
    assert result.jobs_removed == 1

    db_session.expire_all()
    jobs = _jobs_by_external_id(db_session, source.id)

    assert jobs["4000001"].content_hash != original_hash
    assert jobs["4000001"].last_content_change_at > original_change_at
    assert jobs["4000001"].status == "active"
    assert jobs["4000002"].status == "active"
    assert jobs["4000003"].status == "closed"


def test_sync_is_idempotent_when_nothing_changes(db_session):
    source = _make_source(db_session)
    payload = copy.deepcopy(FIXTURE)

    with respx.mock:
        respx.get(BOARD_JOBS_URL).mock(return_value=httpx.Response(200, json=payload))
        sync_source(db_session, source.id)

    with respx.mock:
        respx.get(BOARD_JOBS_URL).mock(return_value=httpx.Response(200, json=payload))
        result = sync_source(db_session, source.id)

    assert result.jobs_added == 0
    assert result.jobs_updated == 0
    assert result.jobs_removed == 0

    jobs = db_session.scalars(select(Job).where(Job.job_source_id == source.id)).all()
    assert len(jobs) == 3


def test_sync_records_error_on_failure(db_session, monkeypatch):
    # Collapse the retry/backoff schedule so this test doesn't actually sleep ~40s.
    monkeypatch.setattr("app.providers.greenhouse.client.RETRY_DELAYS", [0])

    source = _make_source(db_session)

    with respx.mock:
        respx.get(BOARD_JOBS_URL).mock(return_value=httpx.Response(500, json={"error": "boom"}))
        try:
            sync_source(db_session, source.id)
        except Exception:
            pass

    db_session.refresh(source)
    assert source.last_error is not None
    assert source.last_attempted_sync is not None
    assert source.last_successful_sync is None
