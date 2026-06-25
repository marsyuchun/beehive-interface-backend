from typing import Any, Dict

import requests

from app.execution.assertions import compare_equals


def assert_status(response: requests.Response, expected_status: int) -> None:
    assert compare_equals(response.status_code, expected_status), (
        f"Expected HTTP {expected_status}, got {response.status_code}. "
        f"Response: {response.text[:1000]}"
    )


def assert_json_contains(actual: Dict[str, Any], expected: Dict[str, Any]) -> None:
    missing_or_different = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if not compare_equals(actual.get(key), value)
    }
    assert not missing_or_different, f"JSON mismatch: {missing_or_different}"
