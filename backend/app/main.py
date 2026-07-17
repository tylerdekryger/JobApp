import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import companies, discover, jobs, profile, sources
from app.logging import configure_logging

configure_logging()

app = FastAPI(title="Job Intelligence Platform API")

# Local-dev CORS: default to any localhost port; override via CORS_ORIGINS (comma-separated) in production.
_env_origins = os.getenv("CORS_ORIGINS", "").strip()
if _env_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _env_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(companies.router)
app.include_router(profile.router)
app.include_router(discover.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
