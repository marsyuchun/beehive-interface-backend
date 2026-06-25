import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExecutionEvent:
    type: str
    run_id: str
    timestamp: str = field(default_factory=utc_timestamp)
    schema_version: str = SCHEMA_VERSION
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "type": self.type,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            **self.payload,
        }


def write_event(path: Path, event: ExecutionEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as event_file:
        event_file.write(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
        )
        event_file.write("\n")
        event_file.flush()
