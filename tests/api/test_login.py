from typing import Any, Dict

import allure
import pytest

from framework.assertions import assert_json_contains, assert_status
from framework.config_loader import load_cases
from framework.http_client import ApiClient


LOGIN_CASES = load_cases("login_cases.yaml")


@allure.feature("用户认证")
@allure.story("登录")
@pytest.mark.regression
@pytest.mark.parametrize("case", LOGIN_CASES, ids=[case["id"] for case in LOGIN_CASES])
def test_login(api_client: ApiClient, case: Dict[str, Any]) -> None:
    payload = {
        key: case[key]
        for key in ("username", "password")
        if key in case
    }

    with allure.step(f"提交登录场景: {case['id']}"):
        response = api_client.post("/api/login", json=payload)

    assert_status(response, case["expected_status"])
    assert_json_contains(response.json(), {"code": case["expected_code"]})
    if case["expected_status"] == 200:
        assert response.json()["access_token"]

