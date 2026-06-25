import json
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.assets import ApiCase, SuiteStep, TestSuite
from app.models.versions import SuiteVersion
from app.schemas.versions import PublishVersion, RestoreVersion
from app.services.assets import list_suite_steps


def _not_found(version_id: int) -> ApiError:
    return ApiError(
        "SUITE_VERSION_NOT_FOUND",
        "Suite version not found.",
        404,
        {"id": version_id},
    )


def _locked_suite(session: Session, suite_id: int) -> TestSuite:
    suite = session.scalar(
        select(TestSuite)
        .options(selectinload(TestSuite.steps).selectinload(SuiteStep.case))
        .where(TestSuite.id == suite_id)
        .with_for_update()
    )
    if suite is None:
        raise ApiError(
            "SUITE_NOT_FOUND",
            "Suite not found.",
            404,
            {"id": suite_id},
        )
    return suite


def _check_revision(suite: TestSuite, draft_revision: int) -> None:
    if suite.draft_revision != draft_revision:
        raise ApiError(
            "SUITE_REVISION_CONFLICT",
            "Suite draft has changed. Refresh before saving.",
            409,
            {"current_revision": suite.draft_revision},
        )


def serialize_case(case: ApiCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "project_id": case.project_id,
        "name": case.name,
        "method": case.method,
        "path": case.path,
        "headers": deepcopy(case.headers_json),
        "query": deepcopy(case.query_json),
        "body": deepcopy(case.body_json),
        "assertions": deepcopy(case.assertions_json),
        "extractors": deepcopy(case.extractors_json),
        "enabled": case.enabled,
    }


def build_suite_snapshot(suite: TestSuite) -> dict[str, Any]:
    return {
        "suite": {
            "name": suite.name,
            "description": suite.description,
        },
        "steps": [
            {
                "step_id": step.id,
                "position": step.position,
                "enabled": step.enabled,
                "case": serialize_case(step.case),
            }
            for step in sorted(suite.steps, key=lambda item: item.position)
        ],
    }


def publish_version(
    session: Session,
    suite_id: int,
    payload: PublishVersion,
) -> SuiteVersion:
    suite = _locked_suite(session, suite_id)
    _check_revision(suite, payload.draft_revision)
    if not any(step.enabled and step.case.enabled for step in suite.steps):
        raise ApiError(
            "SUITE_HAS_NO_ENABLED_STEPS",
            "Suite must contain at least one enabled step.",
            422,
        )

    latest_number = session.scalar(
        select(func.max(SuiteVersion.version_number)).where(
            SuiteVersion.suite_id == suite_id
        )
    )
    version = SuiteVersion(
        suite_id=suite.id,
        version_number=(latest_number or 0) + 1,
        source_revision=suite.draft_revision,
        snapshot_json=build_suite_snapshot(suite),
        change_summary=payload.change_summary,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def list_versions(session: Session, suite_id: int) -> Sequence[SuiteVersion]:
    _locked_suite(session, suite_id)
    return session.scalars(
        select(SuiteVersion)
        .where(SuiteVersion.suite_id == suite_id)
        .order_by(SuiteVersion.version_number.desc())
    ).all()


def get_version(
    session: Session,
    suite_id: int,
    version_id: int,
) -> SuiteVersion:
    version = session.scalar(
        select(SuiteVersion).where(
            SuiteVersion.id == version_id,
            SuiteVersion.suite_id == suite_id,
        )
    )
    if version is None:
        raise _not_found(version_id)
    return version


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def compare_versions(
    session: Session,
    suite_id: int,
    from_version_id: int,
    to_version_id: int,
) -> dict[str, Any]:
    from_version = get_version(session, suite_id, from_version_id)
    to_version = get_version(session, suite_id, to_version_id)
    from_snapshot = from_version.snapshot_json
    to_snapshot = to_version.snapshot_json
    from_order = [
        step["step_id"] for step in from_snapshot.get("steps", [])
    ]
    to_order = [step["step_id"] for step in to_snapshot.get("steps", [])]
    from_steps = {
        step["step_id"]: step for step in from_snapshot.get("steps", [])
    }
    to_steps = {
        step["step_id"]: step for step in to_snapshot.get("steps", [])
    }
    common_ids = from_steps.keys() & to_steps.keys()

    suite_changes = {}
    for field in ("name", "description"):
        old_value = from_snapshot["suite"].get(field)
        new_value = to_snapshot["suite"].get(field)
        if old_value != new_value:
            suite_changes[field] = {"from": old_value, "to": new_value}

    return {
        "from_version_id": from_version.id,
        "to_version_id": to_version.id,
        "suite_changes": suite_changes,
        "added_steps": [
            deepcopy(to_steps[step_id])
            for step_id in to_order
            if step_id not in from_steps
        ],
        "removed_steps": [
            deepcopy(from_steps[step_id])
            for step_id in from_order
            if step_id not in to_steps
        ],
        "reordered_steps": [
            {
                "step_id": step_id,
                "from_position": from_steps[step_id]["position"],
                "to_position": to_steps[step_id]["position"],
            }
            for step_id in from_order
            if step_id in common_ids
            if from_steps[step_id]["position"] != to_steps[step_id]["position"]
        ],
        "changed_cases": [
            {
                "step_id": step_id,
                "from_case": deepcopy(from_steps[step_id]["case"]),
                "to_case": deepcopy(to_steps[step_id]["case"]),
            }
            for step_id in from_order
            if step_id in common_ids
            if _canonical(from_steps[step_id]["case"])
            != _canonical(to_steps[step_id]["case"])
        ],
    }


def _restore_case(
    session: Session,
    project_id: int,
    case_snapshot: dict[str, Any],
) -> ApiCase:
    case = session.get(ApiCase, case_snapshot.get("id"))
    if case is None or case.project_id != project_id:
        case = ApiCase(project_id=project_id)
        session.add(case)

    case.name = case_snapshot["name"]
    case.method = case_snapshot["method"]
    case.path = case_snapshot["path"]
    case.headers_json = deepcopy(case_snapshot.get("headers", {}))
    case.query_json = deepcopy(case_snapshot.get("query", {}))
    case.body_json = deepcopy(case_snapshot.get("body"))
    case.assertions_json = deepcopy(case_snapshot.get("assertions", []))
    case.extractors_json = deepcopy(case_snapshot.get("extractors", []))
    case.enabled = case_snapshot.get("enabled", True)
    session.flush()
    return case


def restore_version(
    session: Session,
    suite_id: int,
    version_id: int,
    payload: RestoreVersion,
) -> tuple[TestSuite, Sequence[SuiteStep]]:
    suite = _locked_suite(session, suite_id)
    _check_revision(suite, payload.draft_revision)
    version = get_version(session, suite_id, version_id)
    snapshot = deepcopy(version.snapshot_json)

    for step in list(suite.steps):
        session.delete(step)
    session.flush()

    suite.name = snapshot["suite"]["name"]
    suite.description = snapshot["suite"].get("description", "")
    for step_snapshot in sorted(
        snapshot.get("steps", []),
        key=lambda item: item["position"],
    ):
        case = _restore_case(session, suite.project_id, step_snapshot["case"])
        session.add(
            SuiteStep(
                suite_id=suite.id,
                case_id=case.id,
                position=step_snapshot["position"],
                enabled=step_snapshot.get("enabled", True),
            )
        )

    suite.draft_revision += 1
    session.commit()
    session.refresh(suite)
    return suite, list_suite_steps(session, suite_id)
