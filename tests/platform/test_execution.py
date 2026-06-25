from unittest.mock import Mock

import httpx
import pytest
import requests

from app.execution.assertions import evaluate_assertions
from app.execution.runner import execute_form_case
from app.execution.variables import (
    ExtractionError,
    UndefinedVariable,
    extract_variables,
    resolve_templates,
)
from framework.http_client import ApiClient


def response_factory(status_code, body):
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("GET", "https://example.test/api"),
    )


def test_resolve_templates_in_nested_request_data():
    value = {
        "url": "/api/users/${user_id}",
        "headers": {"Authorization": "Bearer ${token}"},
        "items": ["${tenant}", 1, True, None],
    }

    assert resolve_templates(
        value,
        {"user_id": 42, "token": "secret", "tenant": "demo"},
    ) == {
        "url": "/api/users/42",
        "headers": {"Authorization": "Bearer secret"},
        "items": ["demo", 1, True, None],
    }


def test_undefined_variable_names_the_missing_value():
    with pytest.raises(UndefinedVariable, match="user_id"):
        resolve_templates("/api/users/${user_id}", {})


def test_evaluate_all_assertions_without_short_circuit():
    response = response_factory(200, {"code": "ERROR", "data": {"items": {}}})

    results = evaluate_assertions(
        response,
        [
            {"type": "status_code", "operator": "equals", "expected": 201},
            {
                "type": "json_value",
                "path": "$.code",
                "operator": "equals",
                "expected": "SUCCESS",
            },
            {
                "type": "json_type",
                "path": "$.data.items",
                "operator": "is",
                "expected": "array",
            },
        ],
    )

    assert len(results) == 3
    assert all(result.passed is False for result in results)


def test_extractors_write_nothing_when_any_extractor_fails():
    context = {"existing": "value"}

    with pytest.raises(ExtractionError, match="missing"):
        extract_variables(
            {"id": 42},
            [
                {"name": "user_id", "path": "$.id"},
                {"name": "missing", "path": "$.missing"},
            ],
            context,
        )

    assert context == {"existing": "value"}


def test_execute_form_case_merges_request_and_commits_extracted_values():
    fake_client = Mock()
    fake_client.request.return_value = response_factory(
        200,
        {"code": "SUCCESS", "data": {"id": 42}},
    )
    context = {"user_id": 42, "token": "secret"}

    result = execute_form_case(
        {
            "name": "查询用户",
            "method": "GET",
            "path": "/api/users/${user_id}",
            "headers": {"Authorization": "Bearer ${token}"},
            "query": {"verbose": True},
            "body": None,
            "assertions": [
                {"type": "status_code", "operator": "equals", "expected": 200},
                {
                    "type": "json_value",
                    "path": "$.code",
                    "operator": "equals",
                    "expected": "SUCCESS",
                },
            ],
            "extractors": [{"name": "result_id", "path": "$.data.id"}],
        },
        {
            "base_url": "https://example.test",
            "headers": {"Accept": "application/json"},
            "variables": {},
            "timeout": 3,
        },
        context,
        lambda: fake_client,
    )

    assert result.passed is True
    assert context["result_id"] == 42
    fake_client.request.assert_called_once_with(
        "GET",
        "https://example.test/api/users/42",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer secret",
        },
        params={"verbose": True},
        json=None,
        timeout=3,
    )


@pytest.mark.parametrize(
    ("method_name", "expected_method"),
    [("put", "PUT"), ("patch", "PATCH"), ("delete", "DELETE")],
)
def test_api_client_supports_mutating_http_methods(
    method_name,
    expected_method,
):
    client = ApiClient("https://example.test")
    response = requests.Response()
    response.status_code = 200
    response._content = b"{}"
    client.session.request = Mock(return_value=response)

    getattr(client, method_name)("/resource", json={"enabled": True})

    assert client.session.request.call_args.args[:2] == (
        expected_method,
        "https://example.test/resource",
    )
