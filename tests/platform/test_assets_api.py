def test_create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": "用户中心 API", "description": "用户服务接口"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "用户中心 API"


def test_project_crud(client):
    created = client.post(
        "/api/v1/projects",
        json={"name": "Billing API", "description": ""},
    ).json()

    listed = client.get("/api/v1/projects")
    updated = client.put(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Billing Platform", "description": "Payments"},
    )
    deleted = client.delete(f"/api/v1/projects/{created['id']}")

    assert [project["id"] for project in listed.json()] == [created["id"]]
    assert updated.json()["name"] == "Billing Platform"
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{created['id']}").status_code == 404


def test_create_environment(client):
    response = client.post(
        "/api/v1/environments",
        json={
            "name": "Test",
            "base_url": "http://127.0.0.1:5000",
            "headers": {"Accept": "application/json"},
            "variables": {"tenant": "demo"},
            "is_default": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_default"] is True


def test_setting_default_environment_clears_previous_default(client):
    first = client.post(
        "/api/v1/environments",
        json={
            "name": "Test",
            "base_url": "http://test.example.com",
            "headers": {},
            "variables": {},
            "is_default": True,
        },
    ).json()
    second = client.post(
        "/api/v1/environments",
        json={
            "name": "Staging",
            "base_url": "https://staging.example.com",
            "headers": {},
            "variables": {},
            "is_default": True,
        },
    ).json()

    environments = client.get("/api/v1/environments").json()

    assert second["is_default"] is True
    assert next(item for item in environments if item["id"] == first["id"])[
        "is_default"
    ] is False


def test_create_case_and_suite(client, project):
    case_response = client.post(
        "/api/v1/cases",
        json={
            "project_id": project["id"],
            "name": "查询用户列表",
            "method": "GET",
            "path": "/api/users",
            "query": {"page": "1"},
            "assertions": [
                {"type": "status_code", "operator": "equals", "expected": 200}
            ],
            "extractors": [],
            "enabled": True,
        },
    )
    suite_response = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "用户中心回归", "description": ""},
    )

    assert case_response.status_code == 201
    assert case_response.json()["method"] == "GET"
    assert suite_response.status_code == 201
    assert suite_response.json()["draft_revision"] == 1


def test_case_path_must_be_relative(client, project):
    response = client.post(
        "/api/v1/cases",
        json={
            "project_id": project["id"],
            "name": "Invalid URL",
            "method": "GET",
            "path": "https://api.example.com/users",
            "assertions": [],
            "extractors": [],
        },
    )

    assert response.status_code == 422
