import allure
import pytest

from framework.assertions import assert_json_contains, assert_status
from framework.http_client import ApiClient


@allure.feature("系统状态")
@allure.story("健康检查")
@allure.title("健康检查接口返回正常")
@pytest.mark.smoke
def test_health_check(api_client: ApiClient) -> None:
    response = api_client.get("/health")

    assert_status(response, 200)
    assert_json_contains(response.json(), {"status": "ok", "service": "mock-api"})

