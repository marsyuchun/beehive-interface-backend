from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import SessionFactory
from app.models.assets import ApiCase, Environment, Project, SuiteStep, TestSuite
from app.models.versions import SuiteVersion
from app.services.versions import build_suite_snapshot


DEMO_PROJECT_NAME = "用户中心 API"
DEMO_SUITE_NAME = "用户中心回归套件"
DEMO_ENVIRONMENT_NAME = "Test"


@dataclass(frozen=True)
class SeedResult:
    project_id: int
    suite_id: int
    environment_id: int
    version_id: int


def _case(
    project_id: int,
    name: str,
    method: str,
    path: str,
    *,
    headers: dict | None = None,
    body=None,
    assertions: list[dict] | None = None,
    extractors: list[dict] | None = None,
) -> ApiCase:
    return ApiCase(
        project_id=project_id,
        name=name,
        method=method,
        path=path,
        headers_json=headers or {},
        query_json={},
        body_json=body,
        assertions_json=assertions
        or [{"type": "status_code", "operator": "equals", "expected": 200}],
        extractors_json=extractors or [],
        enabled=True,
    )


def seed_demo_data(
    session: Session,
    demo_base_url: str = "http://127.0.0.1:5000",
) -> SeedResult:
    project = session.scalar(
        select(Project).where(Project.name == DEMO_PROJECT_NAME)
    )
    if project is None:
        project = Project(
            name=DEMO_PROJECT_NAME,
            description="本地 Mock 用户服务接口演示项目",
        )
        session.add(project)
        session.flush()

    environment = session.scalar(
        select(Environment).where(Environment.name == DEMO_ENVIRONMENT_NAME)
    )
    if environment is None:
        environment = Environment(
            name=DEMO_ENVIRONMENT_NAME,
            base_url=demo_base_url.rstrip("/"),
            headers_json={"Accept": "application/json"},
            variables_json={},
            is_default=True,
        )
        session.add(environment)

    suite = session.scalar(
        select(TestSuite).where(
            TestSuite.project_id == project.id,
            TestSuite.name == DEMO_SUITE_NAME,
        )
    )
    if suite is None:
        suite = TestSuite(
            project_id=project.id,
            name=DEMO_SUITE_NAME,
            description="登录后完成用户增删改查的回归流程",
            draft_revision=7,
        )
        session.add(suite)
    session.flush()

    steps = list(
        session.scalars(
            select(SuiteStep)
            .where(SuiteStep.suite_id == suite.id)
            .order_by(SuiteStep.position)
        ).all()
    )
    if not steps:
        auth_header = {"Authorization": "Bearer ${access_token}"}
        cases = [
            _case(
                project.id,
                "用户登录",
                "POST",
                "/api/login",
                body={"username": "admin", "password": "password123"},
                extractors=[{"name": "access_token", "path": "$.access_token"}],
            ),
            _case(
                project.id,
                "查询用户列表",
                "GET",
                "/api/users",
                headers=auth_header,
            ),
            _case(
                project.id,
                "创建用户",
                "POST",
                "/api/users",
                headers=auth_header,
                body={"username": "demo-user", "display_name": "Demo User"},
                extractors=[{"name": "created_user_id", "path": "$.data.id"}],
            ),
            _case(
                project.id,
                "查询用户详情",
                "GET",
                "/api/users/${created_user_id}",
                headers=auth_header,
            ),
            _case(
                project.id,
                "更新用户",
                "PATCH",
                "/api/users/${created_user_id}",
                headers=auth_header,
                body={"display_name": "Updated Demo User"},
            ),
            _case(
                project.id,
                "删除用户",
                "DELETE",
                "/api/users/${created_user_id}",
                headers=auth_header,
            ),
        ]
        session.add_all(cases)
        session.flush()
        steps = [
            SuiteStep(
                suite_id=suite.id,
                case_id=case.id,
                position=index * 10,
                enabled=True,
            )
            for index, case in enumerate(cases, start=1)
        ]
        session.add_all(steps)
        session.flush()
    suite.steps = steps

    version = session.scalar(
        select(SuiteVersion)
        .where(SuiteVersion.suite_id == suite.id)
        .order_by(SuiteVersion.version_number)
    )
    if version is None:
        version = SuiteVersion(
            suite_id=suite.id,
            version_number=1,
            source_revision=suite.draft_revision,
            snapshot_json=build_suite_snapshot(suite),
            change_summary="初始化演示流程",
        )
        session.add(version)
    session.commit()
    session.refresh(version)
    return SeedResult(
        project_id=project.id,
        suite_id=suite.id,
        environment_id=environment.id,
        version_id=version.id,
    )


def main() -> None:
    settings = Settings()
    with SessionFactory() as session:
        result = seed_demo_data(session, settings.demo_base_url)
    print(
        "Seeded beehive-interface-backend demo data "
        f"(project={result.project_id}, suite={result.suite_id}, "
        f"environment={result.environment_id}, version={result.version_id})"
    )


if __name__ == "__main__":
    main()
