from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.assets import TestSuite, utc_now


class SuiteVersion(Base):
    __tablename__ = "suite_versions"
    __table_args__ = (
        UniqueConstraint(
            "suite_id",
            "version_number",
            name="uq_suite_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    suite_id: Mapped[int] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    suite: Mapped[TestSuite] = relationship(back_populates="versions")
