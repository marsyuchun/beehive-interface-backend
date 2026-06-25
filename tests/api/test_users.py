import allure
import pytest

from framework.assertions import assert_json_contains, assert_status
from framework.http_client import ApiClient


@allure.feature("用户管理")
@allure.story("查询用户")
@allure.title("携带有效 Token 可以查询用户")
@pytest.mark.smoke
def test_get_user_success(authenticated_client: ApiClient) -> None:
    response = authenticated_client.get("/api/users/1")

    assert_status(response, 200)
    body = response.json()
    assert_json_contains(body, {"code": "SUCCESS"})
    assert_json_contains(body["data"], {"id": 1, "username": "admin"})


@allure.feature("用户管理")
@allure.story("查询用户")
@allure.title("未认证请求被拒绝")
@pytest.mark.regression
def test_get_user_without_token(api_client: ApiClient) -> None:
    response = api_client.get("/api/users/1")

    assert_status(response, 401)
    assert_json_contains(response.json(), {"code": "UNAUTHORIZED"})


@allure.feature("用户管理")
@allure.story("查询用户")
@allure.title("查询不存在的用户返回 404")
@pytest.mark.regression
def test_get_missing_user(authenticated_client: ApiClient) -> None:
    response = authenticated_client.get("/api/users/999")

    assert_status(response, 404)
    assert_json_contains(response.json(), {"code": "USER_NOT_FOUND"})

