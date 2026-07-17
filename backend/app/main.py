from fastapi import FastAPI

from app.api.routes import jobs, sources
from app.logging import configure_logging

configure_logging()

app = FastAPI(title="Job Intelligence Platform API")
app.include_router(sources.router)
app.include_router(jobs.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
