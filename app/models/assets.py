from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    suites: Mapped[list[TestSuite]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    cases: Mapped[list[ApiCase]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class TestSuite(TimestampMixin, Base):
    __tablename__ = "test_suites"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    project: Mapped[Project] = relationship(back_populates="suites")
    steps: Mapped[list[SuiteStep]] = relationship(
        back_populates="suite",
        cascade="all, delete-orphan",
        order_by="SuiteStep.position",
    )
    versions: Mapped[list["SuiteVersion"]] = relationship(
        back_populates="suite",
        cascade="all, delete-orphan",
        order_by="SuiteVersion.version_number",
    )


class ApiCase(TimestampMixin, Base):
    __tablename__ = "api_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    headers_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    query_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    body_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    assertions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    extractors_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="cases")
    suite_steps: Mapped[list[SuiteStep]] = relationship(back_populates="case")


class SuiteStep(Base):
    __tablename__ = "suite_steps"
    __table_args__ = (
        UniqueConstraint("suite_id", "position", name="uq_suite_step_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    suite_id: Mapped[int] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("api_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    suite: Mapped[TestSuite] = relationship(back_populates="steps")
    case: Mapped[ApiCase] = relationship(back_populates="suite_steps")


class Environment(TimestampMixin, Base):
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    headers_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    variables_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
