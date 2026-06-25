import re
from copy import deepcopy
from typing import Any

from jsonpath_ng import parse


VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class UndefinedVariable(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Undefined variable: {name}")
        self.name = name


class ExtractionError(ValueError):
    def __init__(self, name: str, path: str) -> None:
        super().__init__(f"Extractor '{name}' found no value at {path}")
        self.name = name
        self.path = path


def _resolve_string(value: str, variables: dict[str, Any]) -> Any:
    full_match = VARIABLE_PATTERN.fullmatch(value)
    if full_match:
        name = full_match.group(1)
        if name not in variables:
            raise UndefinedVariable(name)
        return deepcopy(variables[name])

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise UndefinedVariable(name)
        return str(variables[name])

    return VARIABLE_PATTERN.sub(replace, value)


def resolve_templates(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _resolve_string(value, variables)
    if isinstance(value, dict):
        return {
            key: resolve_templates(item, variables)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [resolve_templates(item, variables) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_templates(item, variables) for item in value)
    return value


def collect_extracted_values(
    response_body: Any,
    extractors: list[dict[str, Any]],
) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    for extractor in extractors:
        name = extractor["name"]
        path = extractor["path"]
        matches = [match.value for match in parse(path).find(response_body)]
        if not matches:
            raise ExtractionError(name, path)
        extracted[name] = matches[0] if len(matches) == 1 else matches
    return extracted


def extract_variables(
    response_body: Any,
    extractors: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    extracted = collect_extracted_values(response_body, extractors)
    context.update(extracted)
    return extracted
