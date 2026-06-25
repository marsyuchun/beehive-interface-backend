import asyncio
import json
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.runs import RunStatus
from app.services.runs import (
    apply_run_event,
    get_run,
    interrupt_stale_runs,
    transition_run,
)


ProcessLauncher = Callable[[list[str]], subprocess.Popen]


def launch_process(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


class JobManager:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        process_launcher: ProcessLauncher = launch_process,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.process_launcher = process_launcher
        self._queue: queue.Queue[tuple[int, Path, Path]] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._current_lock = threading.Lock()
        self._current_run_id: int | None = None
        self._current_process: subprocess.Popen | None = None
        self._subscribers: dict[
            int,
            list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]],
        ] = {}

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        with self.session_factory() as session:
            interrupt_stale_runs(session)
        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._work,
            name="api-pilot-job-manager",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._current_lock:
            process = self._current_process
        if process is not None and process.poll() is None:
            process.terminate()
        if self._worker is not None:
            self._worker.join(timeout=5)

    def enqueue(self, run_id: int, snapshot: dict[str, Any]) -> None:
        self.settings.run_event_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.settings.run_event_dir / f"{run_id}.snapshot.json"
        events_path = self.settings.run_event_dir / f"{run_id}.events.jsonl"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        events_path.write_text("", encoding="utf-8")
        self._queue.put((run_id, snapshot_path, events_path))

    def cancel(self, run_id: int) -> None:
        with self._current_lock:
            if (
                self._current_run_id == run_id
                and self._current_process is not None
                and self._current_process.poll() is None
            ):
                self._current_process.terminate()

    async def subscribe(self, run_id: int) -> asyncio.Queue:
        event_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        self._subscribers.setdefault(run_id, []).append((loop, event_queue))
        return event_queue

    def unsubscribe(self, run_id: int, event_queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(run_id, [])
        self._subscribers[run_id] = [
            item for item in subscribers if item[1] is not event_queue
        ]

    def publish(self, run_id: int, event: dict[str, Any]) -> None:
        for loop, event_queue in list(self._subscribers.get(run_id, [])):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

    def _consume_events(
        self,
        run_id: int,
        events_path: Path,
        offset: int,
    ) -> tuple[int, bool]:
        if not events_path.exists():
            return offset, False
        run_finished = False
        with events_path.open(encoding="utf-8") as event_file:
            event_file.seek(offset)
            for line in event_file:
                if not line.strip():
                    continue
                event = json.loads(line)
                with self.session_factory() as session:
                    apply_run_event(session, run_id, event)
                self.publish(run_id, event)
                if event.get("type") == "run_finished":
                    run_finished = True
            return event_file.tell(), run_finished

    def _work(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_id, snapshot_path, events_path = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._execute(run_id, snapshot_path, events_path)
            finally:
                self._queue.task_done()

    def _execute(
        self,
        run_id: int,
        snapshot_path: Path,
        events_path: Path,
    ) -> None:
        with self.session_factory() as session:
            run = get_run(session, run_id)
            if run.status != RunStatus.QUEUED:
                return
            transition_run(session, run_id, RunStatus.RUNNING)

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "app.execution.plugin",
            "--platform-snapshot",
            str(snapshot_path),
            "--platform-events",
            str(events_path),
            "-q",
        ]
        process = self.process_launcher(command)
        with self._current_lock:
            self._current_run_id = run_id
            self._current_process = process

        offset = 0
        saw_run_finished = False
        terminated_at: float | None = None
        while process.poll() is None and not self._stop_event.is_set():
            offset, finished = self._consume_events(
                run_id,
                events_path,
                offset,
            )
            saw_run_finished = saw_run_finished or finished
            with self.session_factory() as session:
                run = get_run(session, run_id)
                if run.cancel_requested_at and terminated_at is None:
                    process.terminate()
                    terminated_at = time.monotonic()
                elif (
                    terminated_at is not None
                    and time.monotonic() - terminated_at > 5
                ):
                    process.kill()
            time.sleep(0.1)

        offset, finished = self._consume_events(run_id, events_path, offset)
        saw_run_finished = saw_run_finished or finished
        if not saw_run_finished:
            with self.session_factory() as session:
                run = get_run(session, run_id)
                if run.cancel_requested_at is not None:
                    transition_run(session, run_id, RunStatus.CANCELLED)
                elif process.returncode == 0:
                    transition_run(session, run_id, RunStatus.PASSED)
                else:
                    transition_run(session, run_id, RunStatus.ERROR)

        with self._current_lock:
            self._current_run_id = None
            self._current_process = None
