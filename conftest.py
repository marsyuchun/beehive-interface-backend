import logging
import threading
from typing import Dict, Generator

import pytest
from werkzeug.serving import BaseWSGIServer, make_server

from framework.assertions import assert_status
from framework.config_loader import load_environment
from framework.http_client import ApiClient
from framework.logger import configure_logging
from mock_server.app import create_app


LOGGER = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("api-framework")
    group.addoption(
        "--env",
        action="store",
        default="test",
        help="Environment config name from config/<env>.yaml (default: test)",
    )
    group.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Override the configured API base URL and skip the local mock server",
    )


def pytest_configure() -> None:
    configure_logging()


@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Dict[str, object]:
    environment = pytestconfig.getoption("--env")
    return load_environment(environment)


@pytest.fixture(scope="session")
def mock_server() -> Generator[str, None, None]:
    server: BaseWSGIServer = make_server("127.0.0.1", 0, create_app())
    thread = threading.Thread(target=server.serve_forever, name="mock-api-server", daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    LOGGER.info("Local mock server started url=%s", base_url)
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        LOGGER.info("Local mock server stopped")


@pytest.fixture(scope="session")
def api_base_url(
    pytestconfig: pytest.Config,
    settings: Dict[str, object],
    request: pytest.FixtureRequest,
) -> str:
    command_line_url = pytestconfig.getoption("--base-url")
    configured_url = settings.get("base_url")
    if command_line_url:
        return str(command_line_url)
    if configured_url:
        return str(configured_url)
    return request.getfixturevalue("mock_server")


@pytest.fixture
def api_client(
    api_base_url: str,
    settings: Dict[str, object],
) -> Generator[ApiClient, None, None]:
    request_settings = settings["request"]
    assert isinstance(request_settings, dict)
    client = ApiClient(
        base_url=api_base_url,
        timeout=float(request_settings["timeout"]),
        headers=dict(request_settings["headers"]),
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def authenticated_client(api_client: ApiClient) -> ApiClient:
    response = api_client.post(
        "/api/login",
        json={"username": "admin", "password": "password123"},
    )
    assert_status(response, 200)
    api_client.session.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return api_client

