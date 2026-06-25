from sqlalchemy import UniqueConstraint

from app.core.database import Base
from app.models.runs import CaseResultStatus, RunSourceType, RunStatus


def test_platform_metadata_contains_all_domain_tables():
    assert set(Base.metadata.tables) == {
        "projects",
        "test_suites",
        "api_cases",
        "suite_steps",
        "environments",
        "suite_versions",
        "test_runs",
        "case_results",
    }


def test_order_version_and_result_keys_are_unique_within_parent():
    expected_constraints = {
        "suite_steps": {"suite_id", "position"},
        "suite_versions": {"suite_id", "version_number"},
        "case_results": {"run_id", "case_key"},
    }

    for table_name, expected_columns in expected_constraints.items():
        constraints = Base.metadata.tables[table_name].constraints
        unique_column_sets = {
            frozenset(column.name for column in constraint.columns)
            for constraint in constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert frozenset(expected_columns) in unique_column_sets


def test_run_enums_use_stable_string_values():
    assert {status.value for status in RunStatus} == {
        "QUEUED",
        "RUNNING",
        "PASSED",
        "FAILED",
        "CANCELLED",
        "ERROR",
        "INTERRUPTED",
    }
    assert {source.value for source in RunSourceType} == {
        "FORM_SUITE",
        "PYTHON_TESTS",
    }
    assert {status.value for status in CaseResultStatus} == {
        "PASSED",
        "FAILED",
        "SKIPPED",
        "ERROR",
    }
