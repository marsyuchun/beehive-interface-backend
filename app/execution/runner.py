from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable, Protocol
from urllib.parse import urljoin

import httpx

from app.execution.assertions import AssertionResult, evaluate_assertions
from app.execution.variables import (
    collect_extracted_values,
    resolve_templates,
)


class RequestClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...

    def close(self) -> None: ...


@dataclass
class CaseExecutionResult:
    name: str
    passed: bool
    duration_ms: float
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    assertions: list[AssertionResult]
    extracted_variables: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _response_body(response: Any) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def execute_form_case(
    case: dict[str, Any],
    environment: dict[str, Any],
    context: dict[str, Any],
    client_factory: Callable[[], RequestClient] | None = None,
) -> CaseExecutionResult:
    started_at = perf_counter()
    request_record: dict[str, Any] | None = None
    response_record: dict[str, Any] | None = None
    assertion_results: list[AssertionResult] = []
    extracted_variables: dict[str, Any] = {}
    client: RequestClient | None = None
    owns_client = client_factory is None

    try:
        variables = {
            **environment.get("variables", {}),
            **context,
        }
        path = resolve_templates(case["path"], variables)
        url = urljoin(
            environment["base_url"].rstrip("/") + "/",
            str(path).lstrip("/"),
        )
        headers = resolve_templates(
            {
                **environment.get("headers", {}),
                **case.get("headers", {}),
            },
            variables,
        )
        query = resolve_templates(case.get("query", {}), variables)
        body = resolve_templates(case.get("body"), variables)
        timeout = environment.get(
            "timeout",
            environment.get("timeout_seconds", 10),
        )
        method = case["method"].upper()
        request_record = {
            "method": method,
            "url": url,
            "headers": headers,
            "query": query,
            "body": body,
        }

        client = client_factory() if client_factory else httpx.Client()
        response = client.request(
            method,
            url,
            headers=headers,
            params=query,
            json=body,
            timeout=timeout,
        )
        response_body = _response_body(response)
        response_record = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
        }
        assertion_results = evaluate_assertions(
            response,
            case.get("assertions", []),
        )
        extracted_variables = collect_extracted_values(
            response_body,
            case.get("extractors", []),
        )
        context.update(extracted_variables)
        passed = all(result.passed for result in assertion_results)
        return CaseExecutionResult(
            name=case["name"],
            passed=passed,
            duration_ms=(perf_counter() - started_at) * 1000,
            request=request_record,
            response=response_record,
            assertions=assertion_results,
            extracted_variables=extracted_variables,
        )
    except Exception as error:
        return CaseExecutionResult(
            name=case.get("name", "Unnamed case"),
            passed=False,
            duration_ms=(perf_counter() - started_at) * 1000,
            request=request_record,
            response=response_record,
            assertions=assertion_results,
            extracted_variables={},
            error=str(error),
        )
    finally:
        if owns_client and client is not None:
            client.close()
