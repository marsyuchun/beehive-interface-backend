from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.runs import CaseResultStatus, RunSourceType, RunStatus
from app.schemas.assets import StrictSchema


class RunCreate(StrictSchema):
    suite_id: int
    suite_version_id: int | None = None
    environment_id: int
    source_type: RunSourceType = RunSourceType.FORM_SUITE


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    suite_id: int | None
    suite_version_id: int | None
    draft_revision: int | None
    environment_id: int | None
    source_type: RunSourceType
    status: RunStatus
    total: int
    completed: int
    passed: int
    failed: int
    skipped: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None
    error_message: str | None


class CaseResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    case_key: str
    case_name: str
    sequence: int
    status: CaseResultStatus
    duration_ms: float
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    assertions: list[dict[str, Any]]
    extracted_variables: dict[str, Any]
    error_message: str | None

    @classmethod
    def from_result(cls, result) -> "CaseResultRead":
        return cls(
            id=result.id,
            run_id=result.run_id,
            case_key=result.case_key,
            case_name=result.case_name,
            sequence=result.sequence,
            status=result.status,
            duration_ms=result.duration_ms,
            request=result.request_json,
            response=result.response_json,
            assertions=result.assertions_json,
            extracted_variables=result.extracted_variables_json,
            error_message=result.error_message,
        )
