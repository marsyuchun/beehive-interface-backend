from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.assets import ApiCase, Environment, Project, SuiteStep, TestSuite
from app.schemas.assets import (
    CaseCreate,
    CaseUpdate,
    EnvironmentCreate,
    EnvironmentUpdate,
    ProjectCreate,
    ProjectUpdate,
    SuiteCreate,
    SuiteStepCreate,
    SuiteStepOrder,
    SuiteUpdate,
)


def _commit(session: Session, conflict_code: str, conflict_message: str) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiError(conflict_code, conflict_message, 409) from error


def _not_found(resource: str, resource_id: int) -> ApiError:
    return ApiError(
        code=f"{resource.upper()}_NOT_FOUND",
        message=f"{resource.replace('_', ' ').title()} not found.",
        status_code=404,
        details={"id": resource_id},
    )


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project = Project(**payload.model_dump())
    session.add(project)
    _commit(session, "PROJECT_NAME_CONFLICT", "Project name already exists.")
    session.refresh(project)
    return project


def list_projects(session: Session) -> Sequence[Project]:
    return session.scalars(select(Project).order_by(Project.id)).all()


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise _not_found("project", project_id)
    return project


def update_project(
    session: Session,
    project_id: int,
    payload: ProjectUpdate,
) -> Project:
    project = get_project(session, project_id)
    for field, value in payload.model_dump().items():
        setattr(project, field, value)
    _commit(session, "PROJECT_NAME_CONFLICT", "Project name already exists.")
    session.refresh(project)
    return project


def delete_project(session: Session, project_id: int) -> None:
    project = get_project(session, project_id)
    session.delete(project)
    session.commit()


def create_suite(
    session: Session,
    project_id: int,
    payload: SuiteCreate,
) -> TestSuite:
    get_project(session, project_id)
    suite = TestSuite(project_id=project_id, **payload.model_dump())
    session.add(suite)
    session.commit()
    session.refresh(suite)
    return suite


def list_suites(session: Session, project_id: int) -> Sequence[TestSuite]:
    get_project(session, project_id)
    return session.scalars(
        select(TestSuite)
        .where(TestSuite.project_id == project_id)
        .order_by(TestSuite.id)
    ).all()


def get_suite(session: Session, suite_id: int) -> TestSuite:
    suite = session.get(TestSuite, suite_id)
    if suite is None:
        raise _not_found("suite", suite_id)
    return suite


def update_suite(
    session: Session,
    suite_id: int,
    payload: SuiteUpdate,
) -> TestSuite:
    suite = get_suite(session, suite_id)
    if suite.draft_revision != payload.draft_revision:
        raise ApiError(
            "SUITE_REVISION_CONFLICT",
            "Suite draft has changed. Refresh before saving.",
            409,
            {"current_revision": suite.draft_revision},
        )
    suite.name = payload.name
    suite.description = payload.description
    suite.draft_revision += 1
    session.commit()
    session.refresh(suite)
    return suite


def delete_suite(session: Session, suite_id: int) -> None:
    suite = get_suite(session, suite_id)
    session.delete(suite)
    session.commit()


def _clear_default_environments(session: Session) -> None:
    session.execute(update(Environment).values(is_default=False))


def create_environment(
    session: Session,
    payload: EnvironmentCreate,
) -> Environment:
    if payload.is_default:
        _clear_default_environments(session)
    environment = Environment(
        name=payload.name,
        base_url=payload.base_url,
        headers_json=payload.headers,
        variables_json=payload.variables,
        is_default=payload.is_default,
    )
    session.add(environment)
    _commit(
        session,
        "ENVIRONMENT_NAME_CONFLICT",
        "Environment name already exists.",
    )
    session.refresh(environment)
    return environment


def list_environments(session: Session) -> Sequence[Environment]:
    return session.scalars(select(Environment).order_by(Environment.id)).all()


def get_environment(session: Session, environment_id: int) -> Environment:
    environment = session.get(Environment, environment_id)
    if environment is None:
        raise _not_found("environment", environment_id)
    return environment


def update_environment(
    session: Session,
    environment_id: int,
    payload: EnvironmentUpdate,
) -> Environment:
    environment = get_environment(session, environment_id)
    if payload.is_default:
        _clear_default_environments(session)
    environment.name = payload.name
    environment.base_url = payload.base_url
    environment.headers_json = payload.headers
    environment.variables_json = payload.variables
    environment.is_default = payload.is_default
    _commit(
        session,
        "ENVIRONMENT_NAME_CONFLICT",
        "Environment name already exists.",
    )
    session.refresh(environment)
    return environment


def delete_environment(session: Session, environment_id: int) -> None:
    environment = get_environment(session, environment_id)
    session.delete(environment)
    session.commit()


def create_case(session: Session, payload: CaseCreate) -> ApiCase:
    get_project(session, payload.project_id)
    case = ApiCase(
        project_id=payload.project_id,
        name=payload.name,
        method=payload.method.value,
        path=payload.path,
        headers_json=payload.headers,
        query_json=payload.query,
        body_json=payload.body,
        assertions_json=[
            assertion.model_dump(mode="json") for assertion in payload.assertions
        ],
        extractors_json=[
            extractor.model_dump(mode="json") for extractor in payload.extractors
        ],
        enabled=payload.enabled,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def list_cases(
    session: Session,
    project_id: int | None = None,
) -> Sequence[ApiCase]:
    statement = select(ApiCase)
    if project_id is not None:
        get_project(session, project_id)
        statement = statement.where(ApiCase.project_id == project_id)
    return session.scalars(statement.order_by(ApiCase.id)).all()


def get_case(session: Session, case_id: int) -> ApiCase:
    case = session.get(ApiCase, case_id)
    if case is None:
        raise _not_found("case", case_id)
    return case


def update_case(
    session: Session,
    case_id: int,
    payload: CaseUpdate,
) -> ApiCase:
    case = get_case(session, case_id)
    get_project(session, payload.project_id)
    case.project_id = payload.project_id
    case.name = payload.name
    case.method = payload.method.value
    case.path = payload.path
    case.headers_json = payload.headers
    case.query_json = payload.query
    case.body_json = payload.body
    case.assertions_json = [
        assertion.model_dump(mode="json") for assertion in payload.assertions
    ]
    case.extractors_json = [
        extractor.model_dump(mode="json") for extractor in payload.extractors
    ]
    case.enabled = payload.enabled
    session.commit()
    session.refresh(case)
    return case


def delete_case(session: Session, case_id: int) -> None:
    case = get_case(session, case_id)
    session.delete(case)
    session.commit()


def _locked_suite(session: Session, suite_id: int) -> TestSuite:
    suite = session.scalar(
        select(TestSuite)
        .where(TestSuite.id == suite_id)
        .with_for_update()
    )
    if suite is None:
        raise _not_found("suite", suite_id)
    return suite


def _check_suite_revision(suite: TestSuite, draft_revision: int) -> None:
    if suite.draft_revision != draft_revision:
        raise ApiError(
            "SUITE_REVISION_CONFLICT",
            "Suite draft has changed. Refresh before saving.",
            409,
            {"current_revision": suite.draft_revision},
        )


def list_suite_steps(session: Session, suite_id: int) -> Sequence[SuiteStep]:
    get_suite(session, suite_id)
    return session.scalars(
        select(SuiteStep)
        .options(selectinload(SuiteStep.case))
        .where(SuiteStep.suite_id == suite_id)
        .order_by(SuiteStep.position)
    ).all()


def _renumber_steps(session: Session, steps: list[SuiteStep]) -> None:
    for index, step in enumerate(steps, start=1):
        step.position = index * -10
    session.flush()
    for index, step in enumerate(steps, start=1):
        step.position = index * 10


def insert_suite_step(
    session: Session,
    suite_id: int,
    payload: SuiteStepCreate,
) -> SuiteStep:
    suite = _locked_suite(session, suite_id)
    _check_suite_revision(suite, payload.draft_revision)
    case = get_case(session, payload.case_id)
    if case.project_id != suite.project_id:
        raise ApiError(
            "CASE_PROJECT_MISMATCH",
            "Case and suite must belong to the same project.",
            422,
        )

    ordered_steps = list(list_suite_steps(session, suite_id))
    anchor_id = payload.before_step_id or payload.after_step_id
    insertion_index = len(ordered_steps)
    if anchor_id is not None:
        anchor_indexes = [
            index
            for index, step in enumerate(ordered_steps)
            if step.id == anchor_id
        ]
        if not anchor_indexes:
            raise ApiError(
                "STEP_ANCHOR_NOT_FOUND",
                "Insertion anchor does not belong to the suite.",
                422,
                {"step_id": anchor_id},
            )
        insertion_index = anchor_indexes[0]
        if payload.after_step_id is not None:
            insertion_index += 1

    new_step = SuiteStep(
        suite_id=suite.id,
        case_id=case.id,
        position=-1_000_000_000,
        enabled=True,
    )
    session.add(new_step)
    session.flush()
    ordered_steps.insert(insertion_index, new_step)
    _renumber_steps(session, ordered_steps)
    suite.draft_revision += 1
    session.commit()
    session.refresh(new_step)
    return session.scalar(
        select(SuiteStep)
        .options(selectinload(SuiteStep.case))
        .where(SuiteStep.id == new_step.id)
    )


def reorder_suite_steps(
    session: Session,
    suite_id: int,
    payload: SuiteStepOrder,
) -> tuple[TestSuite, Sequence[SuiteStep]]:
    suite = _locked_suite(session, suite_id)
    _check_suite_revision(suite, payload.draft_revision)
    current_steps = list(list_suite_steps(session, suite_id))
    current_ids = [step.id for step in current_steps]
    if (
        len(payload.step_ids) != len(set(payload.step_ids))
        or set(payload.step_ids) != set(current_ids)
    ):
        raise ApiError(
            "INVALID_STEP_ORDER",
            "Step order must contain every suite step exactly once.",
            422,
        )

    steps_by_id = {step.id: step for step in current_steps}
    reordered_steps = [steps_by_id[step_id] for step_id in payload.step_ids]
    _renumber_steps(session, reordered_steps)
    suite.draft_revision += 1
    session.commit()
    session.refresh(suite)
    return suite, list_suite_steps(session, suite_id)
