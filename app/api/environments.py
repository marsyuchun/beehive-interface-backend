from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.assets import (
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
)
from app.services import assets

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=EnvironmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_environment(payload: EnvironmentCreate, session: SessionDependency):
    return assets.create_environment(session, payload)


@router.get("", response_model=list[EnvironmentRead])
def list_environments(session: SessionDependency):
    return assets.list_environments(session)


@router.get("/{environment_id}", response_model=EnvironmentRead)
def get_environment(environment_id: int, session: SessionDependency):
    return assets.get_environment(session, environment_id)


@router.put("/{environment_id}", response_model=EnvironmentRead)
def update_environment(
    environment_id: int,
    payload: EnvironmentUpdate,
    session: SessionDependency,
):
    return assets.update_environment(session, environment_id, payload)


@router.delete(
    "/{environment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_environment(
    environment_id: int,
    session: SessionDependency,
) -> Response:
    assets.delete_environment(session, environment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
