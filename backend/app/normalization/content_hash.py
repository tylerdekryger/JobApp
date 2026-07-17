import hashlib

from app.providers.base import NormalizedJob


def compute_content_hash(job: NormalizedJob) -> str:
    parts = [
        job.title,
        job.description,
        job.location or "",
        job.employment_type or "",
        job.department or "",
    ]
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
