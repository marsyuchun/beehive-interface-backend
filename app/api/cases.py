from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.assets import CaseCreate, CaseRead, CaseUpdate
from app.services import assets

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, session: SessionDependency):
    return assets.create_case(session, payload)


@router.get("", response_model=list[CaseRead])
def list_cases(
    session: SessionDependency,
    project_id: int | None = None,
):
    return assets.list_cases(session, project_id)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: int, session: SessionDependency):
    return assets.get_case(session, case_id)


@router.put("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    session: SessionDependency,
):
    return assets.update_case(session, case_id, payload)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: int, session: SessionDependency) -> Response:
    assets.delete_case(session, case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
