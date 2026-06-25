from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Enum as SqlEnum
from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.assets import utc_now


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    INTERRUPTED = "INTERRUPTED"


class RunSourceType(str, Enum):
    FORM_SUITE = "FORM_SUITE"
    PYTHON_TESTS = "PYTHON_TESTS"


class CaseResultStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


def string_enum(enum_type: type[Enum]) -> SqlEnum:
    return SqlEnum(
        enum_type,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
    )


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suite_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_suites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suite_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("suite_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    draft_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[RunSourceType] = mapped_column(
        string_enum(RunSourceType),
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(
        string_enum(RunStatus),
        default=RunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list[CaseResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CaseResult.sequence",
    )


class CaseResult(Base):
    __tablename__ = "case_results"
    __table_args__ = (
        UniqueConstraint("run_id", "case_key", name="uq_run_case_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_key: Mapped[str] = mapped_column(String(512), nullable=False)
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CaseResultStatus] = mapped_column(
        string_enum(CaseResultStatus),
        nullable=False,
    )
    duration_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    request_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    assertions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    extracted_variables_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    run: Mapped[TestRun] = relationship(back_populates="results")
