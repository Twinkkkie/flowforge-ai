import re
from typing import Any

_TEMPLATE = re.compile(r"{{\s*([\w.\-]+)\s*}}")


def get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def render_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if not isinstance(value, str):
        return value

    match = _TEMPLATE.fullmatch(value)
    if match:
        return get_path(context, match.group(1))

    def replace(found: re.Match[str]) -> str:
        resolved = get_path(context, found.group(1))
        return "" if resolved is None else str(resolved)

    return _TEMPLATE.sub(replace, value)
