def create_case(client, project_id, name):
    response = client.post(
        "/api/v1/cases",
        json={
            "project_id": project_id,
            "name": name,
            "method": "GET",
            "path": f"/api/{name}",
            "assertions": [],
            "extractors": [],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_suite(client, project_id):
    response = client.post(
        f"/api/v1/projects/{project_id}/suites",
        json={"name": "回归套件", "description": ""},
    )
    assert response.status_code == 201
    return response.json()


def add_step(client, suite_id, case_id, revision, **position):
    response = client.post(
        f"/api/v1/suites/{suite_id}/steps",
        json={
            "case_id": case_id,
            "draft_revision": revision,
            **position,
        },
    )
    assert response.status_code == 201
    return response.json()


def list_steps(client, suite_id):
    response = client.get(f"/api/v1/suites/{suite_id}/steps")
    assert response.status_code == 200
    return response.json()


def test_insert_step_after_selected_step(client, project):
    suite = create_suite(client, project["id"])
    cases = [
        create_case(client, project["id"], name)
        for name in ("login", "query", "delete")
    ]
    first = add_step(client, suite["id"], cases[0]["id"], 1)
    third = add_step(client, suite["id"], cases[2]["id"], 2)

    response = client.post(
        f"/api/v1/suites/{suite['id']}/steps",
        json={
            "case_id": cases[1]["id"],
            "after_step_id": first["id"],
            "draft_revision": 3,
        },
    )

    assert response.status_code == 201
    assert [step["case_id"] for step in list_steps(client, suite["id"])] == [
        cases[0]["id"],
        cases[1]["id"],
        cases[2]["id"],
    ]
    assert [step["position"] for step in list_steps(client, suite["id"])] == [
        10,
        20,
        30,
    ]
    assert third["id"] != response.json()["id"]


def test_reorder_requires_complete_step_set(client, project):
    suite = create_suite(client, project["id"])
    cases = [
        create_case(client, project["id"], name)
        for name in ("login", "query")
    ]
    first = add_step(client, suite["id"], cases[0]["id"], 1)
    add_step(client, suite["id"], cases[1]["id"], 2)

    response = client.put(
        f"/api/v1/suites/{suite['id']}/steps/order",
        json={"step_ids": [first["id"]], "draft_revision": 3},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_STEP_ORDER"


def test_reorder_updates_all_positions_and_revision(client, project):
    suite = create_suite(client, project["id"])
    cases = [
        create_case(client, project["id"], name)
        for name in ("login", "query", "delete")
    ]
    steps = []
    revision = 1
    for case in cases:
        steps.append(add_step(client, suite["id"], case["id"], revision))
        revision += 1

    response = client.put(
        f"/api/v1/suites/{suite['id']}/steps/order",
        json={
            "step_ids": [step["id"] for step in reversed(steps)],
            "draft_revision": revision,
        },
    )

    assert response.status_code == 200
    assert response.json()["suite"]["draft_revision"] == revision + 1
    assert [step["id"] for step in response.json()["steps"]] == [
        step["id"] for step in reversed(steps)
    ]
    assert [step["position"] for step in response.json()["steps"]] == [
        10,
        20,
        30,
    ]


def test_stale_revision_returns_conflict(client, project):
    suite = create_suite(client, project["id"])
    case = create_case(client, project["id"], "login")

    response = client.post(
        f"/api/v1/suites/{suite['id']}/steps",
        json={"case_id": case["id"], "draft_revision": 0},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "SUITE_REVISION_CONFLICT"


def test_insertion_rejects_before_and_after_together(client, project):
    suite = create_suite(client, project["id"])
    cases = [
        create_case(client, project["id"], name)
        for name in ("login", "query")
    ]
    first = add_step(client, suite["id"], cases[0]["id"], 1)

    response = client.post(
        f"/api/v1/suites/{suite['id']}/steps",
        json={
            "case_id": cases[1]["id"],
            "before_step_id": first["id"],
            "after_step_id": first["id"],
            "draft_revision": 2,
        },
    )

    assert response.status_code == 422
