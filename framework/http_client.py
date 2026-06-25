import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

from framework.logger import redact_url, to_log_text


LOGGER = logging.getLogger(__name__)


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 5,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = urljoin(self.base_url, path.lstrip("/"))
        timeout = kwargs.pop("timeout", self.timeout)
        request_headers = dict(self.session.headers)
        request_headers.update(kwargs.get("headers") or {})

        LOGGER.info(
            "HTTP request method=%s url=%s headers=%s json=%s params=%s",
            method.upper(),
            redact_url(url),
            to_log_text(request_headers),
            to_log_text(kwargs.get("json")),
            to_log_text(kwargs.get("params")),
        )

        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException:
            LOGGER.exception("HTTP request failed method=%s url=%s", method.upper(), redact_url(url))
            raise

        try:
            response_body: Any = response.json()
        except ValueError:
            response_body = response.text[:2000]

        LOGGER.info(
            "HTTP response method=%s url=%s status=%s body=%s",
            method.upper(),
            redact_url(url),
            response.status_code,
            to_log_text(response_body),
        )
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
