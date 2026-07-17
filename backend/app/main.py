from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import companies, jobs, sources
from app.logging import configure_logging

configure_logging()

app = FastAPI(title="Job Intelligence Platform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(companies.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
