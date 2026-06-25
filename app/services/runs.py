from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import redact_secrets
from app.models.assets import Environment, TestSuite
from app.models.runs import (
    CaseResult,
    CaseResultStatus,
    RunSourceType,
    RunStatus,
    TestRun,
)
from app.models.versions import SuiteVersion
from app.schemas.runs import RunCreate


ALLOWED_TRANSITIONS = {
    RunStatus.QUEUED: {
        RunStatus.RUNNING,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    },
    RunStatus.RUNNING: {
        RunStatus.PASSED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.ERROR,
        RunStatus.INTERRUPTED,
    },
}
TERMINAL_STATUSES = {
    RunStatus.PASSED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.ERROR,
    RunStatus.INTERRUPTED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_run(session: Session, run_id: int) -> TestRun:
    run = session.get(TestRun, run_id)
    if run is None:
        raise ApiError(
            "RUN_NOT_FOUND",
            "Test run not found.",
            404,
            {"id": run_id},
        )
    return run


def list_runs(session: Session) -> Sequence[TestRun]:
    return session.scalars(
        select(TestRun).order_by(TestRun.id.desc())
    ).all()


def transition_run(
    session: Session,
    run_id: int,
    target: RunStatus,
) -> TestRun:
    run = get_run(session, run_id)
    if target not in ALLOWED_TRANSITIONS.get(run.status, set()):
        raise ApiError(
            "RUN_STATE_CONFLICT",
            f"Cannot transition run from {run.status.value} to {target.value}.",
            409,
            {"current_status": run.status.value, "target_status": target.value},
        )
    run.status = target
    if target == RunStatus.RUNNING and run.started_at is None:
        run.started_at = utc_now()
    if target in TERMINAL_STATUSES:
        run.finished_at = utc_now()
    session.commit()
    session.refresh(run)
    return run


def create_run(
    session: Session,
    payload: RunCreate,
) -> tuple[TestRun, dict[str, Any]]:
    if payload.source_type != RunSourceType.FORM_SUITE:
        raise ApiError(
            "UNSUPPORTED_RUN_SOURCE",
            "Only FORM_SUITE runs can be created through this endpoint.",
            422,
        )
    suite = session.get(TestSuite, payload.suite_id)
    if suite is None:
        raise ApiError("SUITE_NOT_FOUND", "Suite not found.", 404)
    environment = session.get(Environment, payload.environment_id)
    if environment is None:
        raise ApiError("ENVIRONMENT_NOT_FOUND", "Environment not found.", 404)
    if payload.suite_version_id is None:
        raise ApiError(
            "SUITE_VERSION_REQUIRED",
            "Published suite version is required.",
            422,
        )
    version = session.scalar(
        select(SuiteVersion).where(
            SuiteVersion.id == payload.suite_version_id,
            SuiteVersion.suite_id == suite.id,
        )
    )
    if version is None:
        raise ApiError(
            "SUITE_VERSION_NOT_FOUND",
            "Suite version not found.",
            404,
        )

    steps = deepcopy(version.snapshot_json.get("steps", []))
    total = sum(
        1
        for step in steps
        if step.get("enabled", True)
        and step.get("case", {}).get("enabled", True)
    )
    run = TestRun(
        project_id=suite.project_id,
        suite_id=suite.id,
        suite_version_id=version.id,
        draft_revision=None,
        environment_id=environment.id,
        source_type=payload.source_type,
        status=RunStatus.QUEUED,
        total=total,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    snapshot = {
        "run_id": str(run.id),
        "suite_id": suite.id,
        "suite_version_id": version.id,
        "environment": {
            "base_url": environment.base_url,
            "headers": deepcopy(environment.headers_json),
            "variables": deepcopy(environment.variables_json),
            "timeout": 10,
        },
        "steps": steps,
    }
    return run, snapshot


def list_results(session: Session, run_id: int) -> Sequence[CaseResult]:
    get_run(session, run_id)
    return session.scalars(
        select(CaseResult)
        .where(CaseResult.run_id == run_id)
        .order_by(CaseResult.sequence)
    ).all()


def _result_status(value: str) -> CaseResultStatus:
    try:
        return CaseResultStatus(value)
    except ValueError:
        return CaseResultStatus.ERROR


def apply_run_event(
    session: Session,
    run_id: int,
    event: dict[str, Any],
) -> TestRun:
    run = get_run(session, run_id)
    event_type = event.get("type")
    if event_type == "collection_started":
        run.total = int(event.get("total", run.total))
    elif event_type == "case_started":
        if run.status == RunStatus.QUEUED:
            run.status = RunStatus.RUNNING
            run.started_at = utc_now()
    elif event_type == "case_finished":
        case_key = str(event["case_key"])
        existing = session.scalar(
            select(CaseResult).where(
                CaseResult.run_id == run.id,
                CaseResult.case_key == case_key,
            )
        )
        if existing is None:
            status = _result_status(event.get("status", "ERROR"))
            session.add(
                CaseResult(
                    run_id=run.id,
                    case_key=case_key,
                    case_name=event.get("name", case_key),
                    sequence=int(event.get("sequence", run.completed + 1)),
                    status=status,
                    duration_ms=float(event.get("duration_ms", 0)),
                    request_json=redact_secrets(event.get("request")),
                    response_json=redact_secrets(event.get("response")),
                    assertions_json=redact_secrets(
                        event.get("assertions", [])
                    ),
                    extracted_variables_json=redact_secrets(
                        event.get("extracted_variables", {})
                    ),
                    error_message=event.get("error"),
                )
            )
            run.completed += 1
            if status == CaseResultStatus.PASSED:
                run.passed += 1
            elif status == CaseResultStatus.SKIPPED:
                run.skipped += 1
            else:
                run.failed += 1
    elif event_type == "run_finished" and run.status not in TERMINAL_STATUSES:
        if run.cancel_requested_at is not None:
            run.status = RunStatus.CANCELLED
        elif event.get("status") == "PASSED":
            run.status = RunStatus.PASSED
        else:
            run.status = RunStatus.FAILED
        run.finished_at = utc_now()
    session.commit()
    session.refresh(run)
    return run


def cancel_run(session: Session, run_id: int) -> tuple[TestRun, bool]:
    run = get_run(session, run_id)
    if run.status == RunStatus.QUEUED:
        return transition_run(session, run_id, RunStatus.CANCELLED), False
    if run.status == RunStatus.RUNNING:
        if run.cancel_requested_at is None:
            run.cancel_requested_at = utc_now()
            session.commit()
            session.refresh(run)
        return run, True
    raise ApiError(
        "RUN_STATE_CONFLICT",
        f"Cannot cancel run in {run.status.value} state.",
        409,
        {"current_status": run.status.value},
    )


def interrupt_stale_runs(session: Session) -> int:
    stale_runs = session.scalars(
        select(TestRun).where(
            TestRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING])
        )
    ).all()
    for run in stale_runs:
        run.status = RunStatus.INTERRUPTED
        run.finished_at = utc_now()
    session.commit()
    return len(stale_runs)
