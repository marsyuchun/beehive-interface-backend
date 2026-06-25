from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.versions import (
    PublishVersion,
    RestoredDraft,
    RestoreVersion,
    SuiteVersionRead,
    VersionDiff,
)
from app.services import versions

router = APIRouter(prefix="/api/v1/suites/{suite_id}/versions", tags=["versions"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=SuiteVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def publish_version(
    suite_id: int,
    payload: PublishVersion,
    session: SessionDependency,
):
    return versions.publish_version(session, suite_id, payload)


@router.get("", response_model=list[SuiteVersionRead])
def list_versions(suite_id: int, session: SessionDependency):
    return versions.list_versions(session, suite_id)


@router.get("/compare", response_model=VersionDiff)
def compare_versions(
    suite_id: int,
    session: SessionDependency,
    from_version_id: Annotated[int, Query()],
    to_version_id: Annotated[int, Query()],
):
    return versions.compare_versions(
        session,
        suite_id,
        from_version_id,
        to_version_id,
    )


@router.get("/{version_id}", response_model=SuiteVersionRead)
def get_version(
    suite_id: int,
    version_id: int,
    session: SessionDependency,
):
    return versions.get_version(session, suite_id, version_id)


@router.post("/{version_id}/restore", response_model=RestoredDraft)
def restore_version(
    suite_id: int,
    version_id: int,
    payload: RestoreVersion,
    session: SessionDependency,
):
    suite, steps = versions.restore_version(
        session,
        suite_id,
        version_id,
        payload,
    )
    return {"suite": suite, "steps": steps}
