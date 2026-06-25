from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assets import StrictSchema, SuiteRead, SuiteStepRead


class PublishVersion(StrictSchema):
    draft_revision: int = Field(ge=0)
    change_summary: str = ""


class RestoreVersion(StrictSchema):
    draft_revision: int = Field(ge=0)


class SuiteVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    suite_id: int
    version_number: int
    source_revision: int
    snapshot: dict[str, Any] = Field(validation_alias="snapshot_json")
    change_summary: str
    created_at: datetime


class VersionDiff(BaseModel):
    from_version_id: int
    to_version_id: int
    suite_changes: dict[str, dict[str, Any]]
    added_steps: list[dict[str, Any]]
    removed_steps: list[dict[str, Any]]
    reordered_steps: list[dict[str, Any]]
    changed_cases: list[dict[str, Any]]


class RestoredDraft(BaseModel):
    suite: SuiteRead
    steps: list[SuiteStepRead]
