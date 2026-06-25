from app.models.assets import SuiteStep, TestSuite as SuiteModel


def create_case(client, project_id, name):
    response = client.post(
        "/api/v1/cases",
        json={
            "project_id": project_id,
            "name": name,
            "method": "GET",
            "path": f"/api/{name}",
            "headers": {"Accept": "application/json"},
            "query": {},
            "body": None,
            "assertions": [
                {"type": "status_code", "operator": "equals", "expected": 200}
            ],
            "extractors": [],
            "enabled": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def update_case(client, case, name):
    payload = {
        key: case[key]
        for key in (
            "project_id",
            "method",
            "path",
            "headers",
            "query",
            "body",
            "assertions",
            "extractors",
            "enabled",
        )
    }
    payload["name"] = name
    response = client.put(f"/api/v1/cases/{case['id']}", json=payload)
    assert response.status_code == 200
    return response.json()


def create_suite(client, project_id, name="原始套件"):
    response = client.post(
        f"/api/v1/projects/{project_id}/suites",
        json={"name": name, "description": "回归测试"},
    )
    assert response.status_code == 201
    return response.json()


def add_step(client, suite_id, case_id, revision):
    response = client.post(
        f"/api/v1/suites/{suite_id}/steps",
        json={"case_id": case_id, "draft_revision": revision},
    )
    assert response.status_code == 201
    return response.json()


def publish(client, suite_id, revision, summary):
    response = client.post(
        f"/api/v1/suites/{suite_id}/versions",
        json={"draft_revision": revision, "change_summary": summary},
    )
    assert response.status_code == 201
    return response.json()


def test_publish_version_keeps_case_snapshot_immutable(client, project):
    suite = create_suite(client, project["id"])
    case = create_case(client, project["id"], "原始名称")
    add_step(client, suite["id"], case["id"], 1)

    version = publish(client, suite["id"], 2, "初版")
    update_case(client, case, "已修改名称")

    response = client.get(
        f"/api/v1/suites/{suite['id']}/versions/{version['id']}"
    )

    assert response.status_code == 200
    assert response.json()["version_number"] == 1
    assert response.json()["snapshot"]["steps"][0]["case"]["name"] == "原始名称"


def test_compare_versions_identifies_added_reordered_and_changed_steps(
    client,
    project,
):
    suite = create_suite(client, project["id"])
    first_case = create_case(client, project["id"], "login")
    second_case = create_case(client, project["id"], "query")
    first_step = add_step(client, suite["id"], first_case["id"], 1)
    first_version = publish(client, suite["id"], 2, "初版")

    update_case(client, first_case, "login changed")
    second_step = add_step(client, suite["id"], second_case["id"], 2)
    reordered = client.put(
        f"/api/v1/suites/{suite['id']}/steps/order",
        json={
            "step_ids": [second_step["id"], first_step["id"]],
            "draft_revision": 3,
        },
    )
    assert reordered.status_code == 200
    second_version = publish(client, suite["id"], 4, "新增查询并调整顺序")

    response = client.get(
        f"/api/v1/suites/{suite['id']}/versions/compare",
        params={
            "from_version_id": first_version["id"],
            "to_version_id": second_version["id"],
        },
    )

    assert response.status_code == 200
    diff = response.json()
    assert [item["step_id"] for item in diff["added_steps"]] == [
        second_step["id"]
    ]
    assert diff["removed_steps"] == []
    assert [item["step_id"] for item in diff["reordered_steps"]] == [
        first_step["id"]
    ]
    assert [item["step_id"] for item in diff["changed_cases"]] == [
        first_step["id"]
    ]


def test_compare_versions_identifies_removed_steps(client, project, db_session):
    suite = create_suite(client, project["id"])
    first_case = create_case(client, project["id"], "login")
    second_case = create_case(client, project["id"], "query")
    add_step(client, suite["id"], first_case["id"], 1)
    second_step = add_step(client, suite["id"], second_case["id"], 2)
    first_version = publish(client, suite["id"], 3, "完整版本")

    db_step = db_session.get(SuiteStep, second_step["id"])
    db_session.delete(db_step)
    db_suite = db_session.get(SuiteModel, suite["id"])
    db_suite.draft_revision += 1
    db_session.commit()
    second_version = publish(client, suite["id"], 4, "删除查询")

    response = client.get(
        f"/api/v1/suites/{suite['id']}/versions/compare",
        params={
            "from_version_id": first_version["id"],
            "to_version_id": second_version["id"],
        },
    )

    assert response.status_code == 200
    assert [item["step_id"] for item in response.json()["removed_steps"]] == [
        second_step["id"]
    ]


def test_restore_copies_snapshot_into_draft_without_mutating_history(
    client,
    project,
):
    suite = create_suite(client, project["id"])
    case = create_case(client, project["id"], "原始名称")
    add_step(client, suite["id"], case["id"], 1)
    version = publish(client, suite["id"], 2, "初版")
    update_case(client, case, "已修改名称")
    updated_suite = client.put(
        f"/api/v1/suites/{suite['id']}",
        json={
            "name": "已修改套件",
            "description": "changed",
            "draft_revision": 2,
        },
    ).json()

    response = client.post(
        f"/api/v1/suites/{suite['id']}/versions/{version['id']}/restore",
        json={"draft_revision": updated_suite["draft_revision"]},
    )

    assert response.status_code == 200
    assert response.json()["suite"]["name"] == "原始套件"
    assert response.json()["suite"]["draft_revision"] == 4
    assert response.json()["steps"][0]["case"]["name"] == "原始名称"
    historical = client.get(
        f"/api/v1/suites/{suite['id']}/versions/{version['id']}"
    ).json()
    assert historical["snapshot"]["steps"][0]["case"]["name"] == "原始名称"


def test_publish_rejects_empty_suite(client, project):
    suite = create_suite(client, project["id"])

    response = client.post(
        f"/api/v1/suites/{suite['id']}/versions",
        json={"draft_revision": 1, "change_summary": "empty"},
    )

    assert response.status_code == 422
