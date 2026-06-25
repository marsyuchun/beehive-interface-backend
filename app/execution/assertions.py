from dataclasses import dataclass
from typing import Any, Protocol

from jsonpath_ng import parse


class JsonResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


@dataclass(frozen=True)
class AssertionResult:
    type: str
    passed: bool
    expected: Any
    actual: Any = None
    path: str | None = None
    error: str | None = None


def compare_equals(actual: Any, expected: Any) -> bool:
    return actual == expected


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _json_path_value(body: Any, path: str) -> tuple[Any, str | None]:
    matches = [match.value for match in parse(path).find(body)]
    if not matches:
        return None, f"JSONPath found no value: {path}"
    return (matches[0] if len(matches) == 1 else matches), None


def _evaluate_assertion(
    response: JsonResponse,
    body: Any,
    assertion: dict[str, Any],
) -> AssertionResult:
    assertion_type = assertion.get("type", "")
    expected = assertion.get("expected")
    if assertion_type == "status_code":
        actual = response.status_code
        return AssertionResult(
            type=assertion_type,
            passed=compare_equals(actual, expected),
            expected=expected,
            actual=actual,
        )

    path = assertion.get("path")
    if not path:
        return AssertionResult(
            type=assertion_type,
            passed=False,
            expected=expected,
            error="Assertion path is required.",
        )
    actual, error = _json_path_value(body, path)
    if error:
        return AssertionResult(
            type=assertion_type,
            passed=False,
            expected=expected,
            path=path,
            error=error,
        )
    if assertion_type == "json_value":
        passed = compare_equals(actual, expected)
    elif assertion_type == "json_type":
        actual = json_type_name(actual)
        passed = compare_equals(actual, expected)
    else:
        return AssertionResult(
            type=assertion_type,
            passed=False,
            expected=expected,
            actual=actual,
            path=path,
            error=f"Unsupported assertion type: {assertion_type}",
        )
    return AssertionResult(
        type=assertion_type,
        passed=passed,
        expected=expected,
        actual=actual,
        path=path,
    )


def evaluate_assertions(
    response: JsonResponse,
    assertions: list[dict[str, Any]],
) -> list[AssertionResult]:
    try:
        body = response.json()
    except ValueError:
        body = None
    return [
        _evaluate_assertion(response, body, assertion)
        for assertion in assertions
    ]
