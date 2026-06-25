import json


pytest_plugins = ["pytester"]


def test_platform_plugin_collects_enabled_steps_and_emits_lifecycle_events(
    pytester,
):
    snapshot_path = pytester.path / "snapshot.json"
    events_path = pytester.path / "events.jsonl"
    snapshot_path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "environment": {
                    "base_url": "https://example.test",
                    "headers": {},
                    "variables": {},
                },
                "steps": [
                    {
                        "step_id": 10,
                        "enabled": True,
                        "case": {
                            "name": "health",
                            "method": "GET",
                            "path": "/health",
                            "assertions": [],
                            "extractors": [],
                        },
                    },
                    {
                        "step_id": 20,
                        "enabled": False,
                        "case": {
                            "name": "disabled",
                            "method": "GET",
                            "path": "/disabled",
                            "assertions": [],
                            "extractors": [],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    pytester.makeconftest(
        """
from app.execution.runner import CaseExecutionResult
import app.execution.collector as platform_collector


def fake_execute_form_case(case, environment, context, client_factory=None):
    return CaseExecutionResult(
        name=case["name"],
        passed=True,
        duration_ms=1.25,
        request={"method": "GET", "url": "https://example.test/health"},
        response={"status_code": 200, "body": {"status": "ok"}},
        assertions=[],
        extracted_variables={},
    )


platform_collector.execute_form_case = fake_execute_form_case
"""
    )
    pytester.makepyfile(
        test_standard="""
def test_standard_collection_is_excluded_in_snapshot_mode():
    raise AssertionError("standard tests must not run")
"""
    )

    result = pytester.runpytest(
        "-p",
        "app.execution.plugin",
        "--platform-snapshot",
        str(snapshot_path),
        "--platform-events",
        str(events_path),
        "-q",
    )

    result.assert_outcomes(passed=1)
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in events] == [
        "collection_started",
        "case_started",
        "case_finished",
        "run_finished",
    ]
    assert all(event["schema_version"] == "1.0" for event in events)
    assert all(event["run_id"] == "run-1" for event in events)
    assert events[2]["case_key"] == "10"
    assert events[2]["status"] == "PASSED"
