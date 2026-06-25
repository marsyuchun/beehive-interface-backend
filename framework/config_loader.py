from pathlib import Path
from typing import Any, Dict, List

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"YAML file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file) or {}

    if not isinstance(content, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return content


def load_environment(environment: str) -> Dict[str, Any]:
    if not environment or not environment.replace("-", "_").isalnum():
        raise ValueError(f"Invalid environment name: {environment!r}")

    config = load_yaml(PROJECT_ROOT / "config" / f"{environment}.yaml")
    request_config = config.setdefault("request", {})
    request_config.setdefault("timeout", 5)
    request_config.setdefault("headers", {})
    return config


def load_cases(filename: str) -> List[Dict[str, Any]]:
    content = load_yaml(PROJECT_ROOT / "data" / filename)
    cases = content.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError(f"'cases' must be a list in data/{filename}")
    return cases

