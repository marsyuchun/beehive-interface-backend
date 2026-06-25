import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.runs import CaseResultRead, RunCreate, RunRead
from app.services import runs

router = APIRouter(tags=["runs"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post(
    "/api/v1/runs",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    payload: RunCreate,
    request: Request,
    session: SessionDependency,
):
    run, snapshot = runs.create_run(session, payload)
    manager = getattr(request.app.state, "job_manager", None)
    if manager is not None:
        manager.enqueue(run.id, snapshot)
    return run


@router.get("/api/v1/runs", response_model=list[RunRead])
def list_runs(session: SessionDependency):
    return runs.list_runs(session)


@router.get("/api/v1/runs/{run_id}", response_model=RunRead)
def get_run(run_id: int, session: SessionDependency):
    return runs.get_run(session, run_id)


@router.get(
    "/api/v1/runs/{run_id}/results",
    response_model=list[CaseResultRead],
)
def list_run_results(run_id: int, session: SessionDependency):
    return [
        CaseResultRead.from_result(result)
        for result in runs.list_results(session, run_id)
    ]


@router.post("/api/v1/runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(
    run_id: int,
    request: Request,
    session: SessionDependency,
):
    run, should_terminate = runs.cancel_run(session, run_id)
    manager = getattr(request.app.state, "job_manager", None)
    if should_terminate and manager is not None:
        manager.cancel(run_id)
    return run


@router.websocket("/ws/runs/{run_id}")
async def run_events(
    websocket: WebSocket,
    run_id: int,
    session: SessionDependency,
):
    await websocket.accept()
    manager = getattr(websocket.app.state, "job_manager", None)
    run = runs.get_run(session, run_id)
    await websocket.send_json(
        {
            "type": "run_snapshot",
            "run": RunRead.model_validate(run).model_dump(mode="json"),
        }
    )
    if manager is None:
        await websocket.close()
        return
    event_queue = await manager.subscribe(run_id)
    receive_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            event_task = asyncio.create_task(event_queue.get())
            done, _ = await asyncio.wait(
                {event_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if receive_task in done:
                event_task.cancel()
                await asyncio.gather(event_task, return_exceptions=True)
                if receive_task.cancelled():
                    break
                message = receive_task.result()
                if message["type"] == "websocket.disconnect":
                    break
                receive_task = asyncio.create_task(websocket.receive())
                continue
            await websocket.send_json(event_task.result())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        receive_task.cancel()
        await asyncio.gather(receive_task, return_exceptions=True)
        manager.unsubscribe(run_id, event_queue)
