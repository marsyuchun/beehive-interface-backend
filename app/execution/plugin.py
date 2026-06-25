from pathlib import Path
from typing import Any

import pytest

from app.execution.collector import PlatformCaseItem, load_snapshot
from app.execution.events import ExecutionEvent, write_event


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("beehive-interface-backend")
    group.addoption(
        "--platform-snapshot",
        action="store",
        dest="platform_snapshot",
        help="Path to an immutable beehive-interface-backend run snapshot.",
    )
    group.addoption(
        "--platform-events",
        action="store",
        dest="platform_events",
        help="Path to the JSONL execution event stream.",
    )


def pytest_configure(config: pytest.Config) -> None:
    snapshot_value = config.getoption("platform_snapshot")
    if not snapshot_value:
        return
    events_value = config.getoption("platform_events")
    if not events_value:
        raise pytest.UsageError(
            "--platform-events is required with --platform-snapshot"
        )

    snapshot = load_snapshot(Path(snapshot_value))
    config._api_pilot_snapshot = snapshot
    config._api_pilot_events_path = Path(events_value)
    config._api_pilot_context = {}
    config._api_pilot_items_added = False


def _platform_state(
    config: pytest.Config,
) -> tuple[dict[str, Any], Path, dict[str, Any]] | None:
    snapshot = getattr(config, "_api_pilot_snapshot", None)
    if snapshot is None:
        return None
    return (
        snapshot,
        config._api_pilot_events_path,
        config._api_pilot_context,
    )


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    state = _platform_state(config)
    if state is None or config._api_pilot_items_added:
        return
    snapshot, events_path, context = state
    items.clear()
    enabled_steps = [
        step
        for step in snapshot.get("steps", [])
        if step.get("enabled", True)
        and step.get("case", {}).get("enabled", True)
    ]
    write_event(
        events_path,
        ExecutionEvent(
            type="collection_started",
            run_id=str(snapshot["run_id"]),
            payload={"total": len(enabled_steps)},
        ),
    )
    for sequence, step in enumerate(enabled_steps, start=1):
        items.append(
            PlatformCaseItem.from_parent(
                session,
                name=f"platform[{step['step_id']}] {step['case']['name']}",
                run_id=str(snapshot["run_id"]),
                sequence=sequence,
                step=step,
                environment=snapshot["environment"],
                context=context,
                events_path=events_path,
            )
        )
    config._api_pilot_items_added = True


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    state = _platform_state(session.config)
    if state is None:
        return
    snapshot, events_path, _ = state
    write_event(
        events_path,
        ExecutionEvent(
            type="run_finished",
            run_id=str(snapshot["run_id"]),
            payload={
                "status": "PASSED"
                if exitstatus == pytest.ExitCode.OK
                else "FAILED",
                "exit_code": int(exitstatus),
            },
        ),
    )
