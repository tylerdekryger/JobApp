FROM python:3.12-slim

WORKDIR /srv

COPY backend/ backend/
COPY workers/ workers/

RUN pip install --no-cache-dir -e ./backend

ENV PYTHONPATH=/srv

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info"]
