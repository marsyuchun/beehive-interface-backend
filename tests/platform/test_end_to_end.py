import time
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import Base, get_session
from app.execution.job_manager import JobManager
from app.main import create_app


def _case_payload(
    project_id: int,
    name: str,
    method: str,
    path: str,
    *,
    headers: dict | None = None,
    body=None,
    assertions: list[dict] | None = None,
    extractors: list[dict] | None = None,
) -> dict:
    return {
        "project_id": project_id,
        "name": name,
        "method": method,
        "path": path,
        "headers": headers or {},
        "query": {},
        "body": body,
        "assertions": assertions
        or [{"type": "status_code", "operator": "equals", "expected": 200}],
        "extractors": extractors or [],
        "enabled": True,
    }


def _wait_for_run(
    client: TestClient,
    run_id: int,
    timeout: float = 15,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] in {
            "PASSED",
            "FAILED",
            "CANCELLED",
            "ERROR",
            "INTERRUPTED",
        }:
            return run
        time.sleep(0.1)
    raise AssertionError(f"run {run_id} did not finish within {timeout} seconds")


def test_user_can_build_publish_and_execute_suite(
    tmp_path,
    mock_server,
):
    database_path = tmp_path / "end-to-end.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=database_url,
        run_event_dir=tmp_path / "run-events",
        reports_dir=tmp_path / "reports",
    )
    manager = JobManager(settings, session_factory)
    application = create_app(settings=settings, job_manager=manager)

    def override_get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(application) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={"name": "E2E 用户中心", "description": ""},
            )
            assert project_response.status_code == 201
            project = project_response.json()

            environment_response = client.post(
                "/api/v1/environments",
                json={
                    "name": "E2E Mock",
                    "base_url": mock_server,
                    "headers": {"Accept": "application/json"},
                    "variables": {},
                    "is_default": True,
                },
            )
            assert environment_response.status_code == 201
            environment = environment_response.json()

            login_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "用户登录",
                    "POST",
                    "/api/login",
                    body={
                        "username": "admin",
                        "password": "password123",
                    },
                    extractors=[
                        {"name": "access_token", "path": "$.access_token"}
                    ],
                ),
            )
            assert login_response.status_code == 201

            user_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "查询用户列表",
                    "GET",
                    "/api/users",
                    headers={
                        "Authorization": "Bearer ${access_token}",
                    },
                ),
            )
            assert user_response.status_code == 201

            create_user_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "创建用户",
                    "POST",
                    "/api/users",
                    headers={
                        "Authorization": "Bearer ${access_token}",
                    },
                    body={
                        "username": "e2e-user",
                        "display_name": "E2E User",
                    },
                    extractors=[
                        {"name": "created_user_id", "path": "$.data.id"}
                    ],
                ),
            )
            assert create_user_response.status_code == 201

            detail_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "查询用户详情",
                    "GET",
                    "/api/users/${created_user_id}",
                    headers={
                        "Authorization": "Bearer ${access_token}",
                    },
                    assertions=[
                        {
                            "type": "status_code",
                            "operator": "equals",
                            "expected": 200,
                        },
                        {
                            "type": "json_value",
                            "path": "$.data.username",
                            "operator": "equals",
                            "expected": "e2e-user",
                        },
                    ],
                ),
            )
            assert detail_response.status_code == 201

            update_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "更新用户",
                    "PATCH",
                    "/api/users/${created_user_id}",
                    headers={
                        "Authorization": "Bearer ${access_token}",
                    },
                    body={"display_name": "Updated E2E User"},
                ),
            )
            assert update_response.status_code == 201

            delete_response = client.post(
                "/api/v1/cases",
                json=_case_payload(
                    project["id"],
                    "删除用户",
                    "DELETE",
                    "/api/users/${created_user_id}",
                    headers={
                        "Authorization": "Bearer ${access_token}",
                    },
                ),
            )
            assert delete_response.status_code == 201

            suite_response = client.post(
                f"/api/v1/projects/{project['id']}/suites",
                json={"name": "E2E 回归套件", "description": ""},
            )
            assert suite_response.status_code == 201
            suite = suite_response.json()

            for revision, api_case in enumerate(
                [
                    login_response.json(),
                    user_response.json(),
                    create_user_response.json(),
                    detail_response.json(),
                    update_response.json(),
                    delete_response.json(),
                ],
                start=1,
            ):
                step_response = client.post(
                    f"/api/v1/suites/{suite['id']}/steps",
                    json={
                        "case_id": api_case["id"],
                        "draft_revision": revision,
                    },
                )
                assert step_response.status_code == 201

            version_response = client.post(
                f"/api/v1/suites/{suite['id']}/versions",
                json={
                    "draft_revision": 7,
                    "change_summary": "E2E 可执行版本",
                },
            )
            assert version_response.status_code == 201
            version = version_response.json()

            run_response = client.post(
                "/api/v1/runs",
                json={
                    "suite_id": suite["id"],
                    "suite_version_id": version["id"],
                    "environment_id": environment["id"],
                    "source_type": "FORM_SUITE",
                },
            )
            assert run_response.status_code == 202
            completed = _wait_for_run(client, run_response.json()["id"])

            assert completed["status"] == "PASSED"
            results = client.get(
                f"/api/v1/runs/{completed['id']}/results"
            ).json()
            assert len(results) == 6
            assert all(result["status"] == "PASSED" for result in results)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
