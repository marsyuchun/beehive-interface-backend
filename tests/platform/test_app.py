from fastapi import FastAPI

from app.core.errors import ApiError, register_error_handlers


def test_platform_health(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "beehive-interface-backend",
    }


def test_api_error_uses_stable_response_contract():
    application = FastAPI()
    register_error_handlers(application)

    @application.get("/failure")
    def failure():
        raise ApiError(
            code="RESOURCE_CONFLICT",
            message="Resource already exists.",
            status_code=409,
            details={"field": "name"},
        )

    from fastapi.testclient import TestClient

    response = TestClient(application).get("/failure")

    assert response.status_code == 409
    assert response.json() == {
        "code": "RESOURCE_CONFLICT",
        "message": "Resource already exists.",
        "details": {"field": "name"},
    }
