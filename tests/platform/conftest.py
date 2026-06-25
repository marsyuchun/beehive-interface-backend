from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_session
from app.main import create_app


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    application = create_app()

    def override_get_session() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_session] = override_get_session
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def client_with_manager(
    db_session: Session,
    fake_job_manager,
) -> Iterator[TestClient]:
    application = create_app(job_manager=fake_job_manager)

    def override_get_session() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_session] = override_get_session
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": "用户中心 API", "description": "用户服务接口"},
    )
    assert response.status_code == 201
    return response.json()
