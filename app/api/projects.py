from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.assets import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    SuiteCreate,
    SuiteRead,
    SuiteStepCreate,
    SuiteStepOrder,
    SuiteStepRead,
    SuiteStepsRead,
    SuiteUpdate,
)
from app.services import assets

router = APIRouter(prefix="/api/v1", tags=["projects"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(payload: ProjectCreate, session: SessionDependency):
    return assets.create_project(session, payload)


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(session: SessionDependency):
    return assets.list_projects(session)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: SessionDependency):
    return assets.get_project(session, project_id)


@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: SessionDependency,
):
    return assets.update_project(session, project_id, payload)


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(project_id: int, session: SessionDependency) -> Response:
    assets.delete_project(session, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/suites",
    response_model=SuiteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_suite(
    project_id: int,
    payload: SuiteCreate,
    session: SessionDependency,
):
    return assets.create_suite(session, project_id, payload)


@router.get(
    "/projects/{project_id}/suites",
    response_model=list[SuiteRead],
)
def list_suites(project_id: int, session: SessionDependency):
    return assets.list_suites(session, project_id)


@router.get("/suites/{suite_id}", response_model=SuiteRead)
def get_suite(suite_id: int, session: SessionDependency):
    return assets.get_suite(session, suite_id)


@router.put("/suites/{suite_id}", response_model=SuiteRead)
def update_suite(
    suite_id: int,
    payload: SuiteUpdate,
    session: SessionDependency,
):
    return assets.update_suite(session, suite_id, payload)


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(suite_id: int, session: SessionDependency) -> Response:
    assets.delete_suite(session, suite_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/suites/{suite_id}/steps",
    response_model=list[SuiteStepRead],
)
def list_suite_steps(suite_id: int, session: SessionDependency):
    return assets.list_suite_steps(session, suite_id)


@router.post(
    "/suites/{suite_id}/steps",
    response_model=SuiteStepRead,
    status_code=status.HTTP_201_CREATED,
)
def insert_suite_step(
    suite_id: int,
    payload: SuiteStepCreate,
    session: SessionDependency,
):
    return assets.insert_suite_step(session, suite_id, payload)


@router.put(
    "/suites/{suite_id}/steps/order",
    response_model=SuiteStepsRead,
)
def reorder_suite_steps(
    suite_id: int,
    payload: SuiteStepOrder,
    session: SessionDependency,
):
    suite, steps = assets.reorder_suite_steps(session, suite_id, payload)
    return {"suite": suite, "steps": steps}
