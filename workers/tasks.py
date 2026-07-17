from app.db import SessionLocal
from app.sync.sync_service import sync_source
from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.sync_source_task")
def sync_source_task(source_id: int) -> dict:
    session = SessionLocal()
    try:
        result = sync_source(session, source_id)
    finally:
        session.close()
    return {
        "source_id": result.source_id,
        "jobs_found": result.jobs_found,
        "jobs_added": result.jobs_added,
        "jobs_updated": result.jobs_updated,
        "jobs_removed": result.jobs_removed,
        "duration_seconds": result.duration_seconds,
    }
