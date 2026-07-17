from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("job_intelligence", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "sync"
celery_app.autodiscover_tasks(["workers"])
