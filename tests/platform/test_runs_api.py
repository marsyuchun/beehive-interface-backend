from datetime import datetime, timezone
import asyncio

import pytest

from app.api.runs import run_events
from app.core.errors import ApiError
from app.models.runs import RunStatus, TestRun as RunModel
from app.services.runs import apply_run_event, transition_run


class FakeJobManager:
    def __init__(self):
        self.enqueued = []
        self.cancelled = []
        self.unsubscribed = []

    def enqueue(self, run_id, snapshot):
        self.enqueued.append((run_id, snapshot))

    def cancel(self, run_id):
        self.cancelled.append(run_id)

    async def subscribe(self, run_id):
        event_queue = asyncio.Queue()
        await event_queue.put(
            {"type": "case_started", "run_id": str(run_id), "case_key": "10"}
        )
        return event_queue

    def unsubscribe(self, run_id, event_queue):
        self.unsubscribed.append((run_id, event_queue))


@pytest.fixture
def fake_job_manager():
    return FakeJobManager()


def create_published_suite(client):
    project = client.post(
        "/api/v1/projects",
        json={"name": "用户中心 API", "description": ""},
    ).json()
    environment = client.post(
        "/api/v1/environments",
        json={
            "name": "Test",
            "base_url": "https://example.test",
            "headers": {"Authorization": "Bearer demo"},
            "variables": {"tenant": "demo"},
            "is_default": True,
        },
    ).json()
    case = client.post(
        "/api/v1/cases",
        json={
            "project_id": project["id"],
            "name": "health",
            "method": "GET",
            "path": "/health",
            "assertions": [
                {"type": "status_code", "operator": "equals", "expected": 200}
            ],
            "extractors": [],
        },
    ).json()
    suite = client.post(
        f"/api/v1/projects/{project['id']}/suites",
        json={"name": "回归套件", "description": ""},
    ).json()
    client.post(
        f"/api/v1/suites/{suite['id']}/steps",
        json={"case_id": case["id"], "draft_revision": 1},
    )
    version = client.post(
        f"/api/v1/suites/{suite['id']}/versions",
        json={"draft_revision": 2, "change_summary": "初版"},
    ).json()
    return project, environment, suite, version


def create_run(client):
    project, environment, suite, version = create_published_suite(client)
    response = client.post(
        "/api/v1/runs",
        json={
            "suite_id": suite["id"],
            "suite_version_id": version["id"],
            "environment_id": environment["id"],
            "source_type": "FORM_SUITE",
        },
    )
    return response, project, environment, suite, version


def test_create_run_queues_suite_snapshot(
    client_with_manager,
    fake_job_manager,
):
    response, project, environment, suite, version = create_run(
        client_with_manager
    )

    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    assert response.json()["project_id"] == project["id"]
    run_id, snapshot = fake_job_manager.enqueued[0]
    assert run_id == response.json()["id"]
    assert snapshot["run_id"] == str(run_id)
    assert snapshot["environment"]["base_url"] == environment["base_url"]
    assert snapshot["steps"][0]["case"]["name"] == "health"


def test_case_finished_event_updates_counters_and_persists_result(
    client_with_manager,
    db_session,
):
    response, *_ = create_run(client_with_manager)
    run_id = response.json()["id"]

    apply_run_event(
        db_session,
        run_id,
        {
            "type": "case_finished",
            "case_key": "10",
            "name": "health",
            "sequence": 1,
            "status": "PASSED",
            "duration_ms": 12.5,
            "request": {"headers": {"Authorization": "secret"}},
            "response": {"status_code": 200},
            "assertions": [{"passed": True}],
            "extracted_variables": {"token": "secret"},
            "error": None,
        },
    )

    detail = client_with_manager.get(f"/api/v1/runs/{run_id}").json()
    results = client_with_manager.get(
        f"/api/v1/runs/{run_id}/results"
    ).json()
    assert detail["completed"] == 1
    assert detail["passed"] == 1
    assert results[0]["case_key"] == "10"
    assert results[0]["request"]["headers"]["Authorization"] == "***REDACTED***"
    assert results[0]["extracted_variables"]["token"] == "***REDACTED***"


def test_cancel_queued_run_marks_it_cancelled_immediately(
    client_with_manager,
    fake_job_manager,
):
    response, *_ = create_run(client_with_manager)
    run_id = response.json()["id"]

    cancelled = client_with_manager.post(f"/api/v1/runs/{run_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert fake_job_manager.cancelled == []


def test_cancel_running_run_requests_process_termination(
    client_with_manager,
    fake_job_manager,
    db_session,
):
    response, *_ = create_run(client_with_manager)
    run_id = response.json()["id"]
    transition_run(db_session, run_id, RunStatus.RUNNING)

    cancelled = client_with_manager.post(f"/api/v1/runs/{run_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "RUNNING"
    assert cancelled.json()["cancel_requested_at"] is not None
    assert fake_job_manager.cancelled == [run_id]


def test_invalid_state_transition_returns_conflict(db_session):
    run = RunModel(
        source_type="FORM_SUITE",
        status=RunStatus.PASSED,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.commit()

    with pytest.raises(ApiError) as exc_info:
        transition_run(db_session, run.id, RunStatus.RUNNING)

    assert getattr(exc_info.value, "code", None) == "RUN_STATE_CONFLICT"


def test_websocket_sends_snapshot_before_live_events(client_with_manager):
    response, *_ = create_run(client_with_manager)
    run_id = response.json()["id"]

    with client_with_manager.websocket_connect(
        f"/ws/runs/{run_id}"
    ) as websocket:
        snapshot = websocket.receive_json()
        live_event = websocket.receive_json()

    assert snapshot["type"] == "run_snapshot"
    assert snapshot["run"]["id"] == run_id
    assert live_event["type"] == "case_started"


def test_websocket_observes_disconnect_while_event_queue_is_idle(
    client_with_manager,
    db_session,
):
    response, *_ = create_run(client_with_manager)
    run_id = response.json()["id"]

    class IdleManager:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.unsubscribed = []

        async def subscribe(self, subscribed_run_id):
            assert subscribed_run_id == run_id
            return self.queue

        def unsubscribe(self, subscribed_run_id, event_queue):
            self.unsubscribed.append((subscribed_run_id, event_queue))

    class DisconnectingWebSocket:
        def __init__(self, manager):
            self.app = type(
                "App",
                (),
                {"state": type("State", (), {"job_manager": manager})()},
            )()
            self.receive_calls = 0
            self.messages = []

        async def accept(self):
            return None

        async def send_json(self, message):
            self.messages.append(message)

        async def receive(self):
            self.receive_calls += 1
            return {"type": "websocket.disconnect"}

        async def close(self):
            return None

    manager = IdleManager()
    websocket = DisconnectingWebSocket(manager)

    asyncio.run(
        asyncio.wait_for(
            run_events(websocket, run_id, db_session),
            timeout=0.1,
        )
    )

    assert websocket.messages[0]["type"] == "run_snapshot"
    assert websocket.receive_calls == 1
    assert manager.unsubscribed == [(run_id, manager.queue)]
