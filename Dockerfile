# Backend-only image for Fly.io deployment.
# Frontend deploys separately to Vercel.
FROM python:3.12-slim

# Runtime deps for psycopg + smtplib TLS + healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Install first so subsequent code changes don't reinstall deps.
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/app backend/app
COPY backend/alembic backend/alembic
COPY backend/alembic.ini backend/alembic.ini
COPY workers workers

RUN pip install --no-cache-dir -e ./backend

ENV PYTHONPATH=/srv
ENV PORT=8080
EXPOSE 8080

# Run migrations on release_command in fly.toml, then launch the API.
CMD ["sh", "-c", "cd backend && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
