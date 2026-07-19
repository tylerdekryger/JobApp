import hashlib

from app.providers.base import NormalizedJob


def compute_content_hash(job: NormalizedJob) -> str:
    """Hash of fields that come directly from the upstream source.

    Derived fields (remote_type, cleaned department) are intentionally excluded — otherwise
    a change to our normalization logic would flag every existing job as "updated" on the
    next sync even though the source didn't touch it.
    """
    parts = [
        job.title,
        job.description,
        job.location or "",
        f"{job.salary_min or ''}|{job.salary_max or ''}|{job.salary_currency or ''}",
    ]
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
