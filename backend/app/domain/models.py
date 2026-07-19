from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sources: Mapped[list["JobSource"]] = relationship(back_populates="company")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class JobSource(Base):
    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("provider", "source_identifier", name="uq_job_sources_provider_identifier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(String(2048))
    source_identifier: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempted_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_boilerplate_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="sources")
    jobs: Mapped[list["Job"]] = relationship(back_populates="job_source")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("job_source_id", "external_job_id", name="uq_jobs_source_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    job_source_id: Mapped[int] = mapped_column(ForeignKey("job_sources.id"), index=True)
    external_job_id: Mapped[str] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_content_change_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="active")
    # Set when a previously-closed job reappears on a source's board. first_seen_at is preserved
    # as the ORIGINAL discovery date so the UI can show both "first seen" and "reposted".
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    # LLM-scored fit/gap against the current user resume; cleared when the resume changes.
    fit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_resume_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cross-referenced context from external sources (LinkedIn) — helps flag reposted /
    # long-open roles whose Ashby "publishedAt" was bumped but which have been actively
    # circulating for months.
    market_check_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_check_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    market_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="jobs")
    job_source: Mapped["JobSource"] = relationship(back_populates="jobs")


class UserProfile(Base):
    """Single-row settings table (id=1) for the local user's resume."""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_text: Mapped[str] = mapped_column(Text, default="")
    resume_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
