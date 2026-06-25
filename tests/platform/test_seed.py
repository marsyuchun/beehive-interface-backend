from sqlalchemy import func, select

from app.models.assets import Environment, Project, SuiteStep
from app.models.assets import TestSuite as SuiteModel
from app.models.versions import SuiteVersion
from app.seed import seed_demo_data


def test_seed_demo_data_is_idempotent(db_session):
    first = seed_demo_data(db_session)
    second = seed_demo_data(db_session)

    assert first.project_id == second.project_id
    assert first.suite_id == second.suite_id
    assert first.version_id == second.version_id
    assert db_session.scalar(select(func.count(Project.id))) == 1
    assert db_session.scalar(select(func.count(SuiteStep.id))) == 6
    assert db_session.scalar(select(func.count(SuiteVersion.id))) == 1


def test_seed_recovers_from_partially_initialized_project(db_session):
    project = Project(name="用户中心 API", description="partial")
    db_session.add(project)
    db_session.commit()

    result = seed_demo_data(db_session)

    assert result.project_id == project.id
    assert db_session.scalar(select(func.count(Environment.id))) == 1
    assert db_session.scalar(select(func.count(SuiteModel.id))) == 1
    assert db_session.scalar(select(func.count(SuiteStep.id))) == 6
    assert db_session.scalar(select(func.count(SuiteVersion.id))) == 1


def test_seed_uses_configured_demo_base_url(db_session):
    result = seed_demo_data(db_session, "http://mock-api:5000/")

    environment = db_session.get(Environment, result.environment_id)

    assert environment is not None
    assert environment.base_url == "http://mock-api:5000"
