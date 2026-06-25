import json
from pathlib import Path
from typing import Any

import pytest

from app.core.security import redact_secrets
from app.execution.events import ExecutionEvent, write_event
from app.execution.runner import execute_form_case


def load_snapshot(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as snapshot_file:
        return json.load(snapshot_file)


class PlatformCaseItem(pytest.Item):
    def __init__(
        self,
        name: str,
        parent: pytest.Collector,
        *,
        run_id: str,
        sequence: int,
        step: dict[str, Any],
        environment: dict[str, Any],
        context: dict[str, Any],
        events_path: Path,
    ) -> None:
        super().__init__(name, parent)
        self.run_id = run_id
        self.sequence = sequence
        self.step = step
        self.environment = environment
        self.context = context
        self.events_path = events_path
        self.add_marker("platform")

    @property
    def case_key(self) -> str:
        return str(self.step["step_id"])

    def runtest(self) -> None:
        case = self.step["case"]
        write_event(
            self.events_path,
            ExecutionEvent(
                type="case_started",
                run_id=self.run_id,
                payload={
                    "case_key": self.case_key,
                    "name": case["name"],
                    "sequence": self.sequence,
                },
            ),
        )
        result = execute_form_case(case, self.environment, self.context)
        result_payload = result.to_dict()
        write_event(
            self.events_path,
            ExecutionEvent(
                type="case_finished",
                run_id=self.run_id,
                payload={
                    "case_key": self.case_key,
                    "name": result.name,
                    "sequence": self.sequence,
                    "status": "PASSED" if result.passed else "FAILED",
                    "duration_ms": result.duration_ms,
                    "request": redact_secrets(result.request),
                    "response": redact_secrets(result.response),
                    "assertions": redact_secrets(result_payload["assertions"]),
                    "extracted_variables": redact_secrets(
                        result.extracted_variables
                    ),
                    "error": result.error,
                },
            ),
        )
        if not result.passed:
            raise AssertionError(result.error or f"Case failed: {result.name}")

    def repr_failure(self, excinfo, style=None):
        return str(excinfo.value)

    def reportinfo(self):
        snapshot_path = Path(str(self.config.getoption("platform_snapshot")))
        return snapshot_path, self.sequence, self.name
