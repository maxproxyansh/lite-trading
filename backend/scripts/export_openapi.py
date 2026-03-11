from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.routing import APIRoute


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402


def _find_rate_limit_metadata(route: APIRoute) -> dict | None:
    stack = list(route.dependant.dependencies)
    while stack:
        dependant = stack.pop()
        metadata = getattr(dependant.call, "__lite_rate_limit__", None)
        if metadata:
            return metadata
        stack.extend(dependant.dependencies)
    return None


def main() -> None:
    openapi = app.openapi()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        metadata = _find_rate_limit_metadata(route)
        if not metadata:
            continue
        for method in route.methods:
            operation = openapi["paths"].get(route.path, {}).get(method.lower())
            if operation is not None:
                operation["x-ratelimit"] = metadata

    output = ROOT / "backend" / "openapi.json"
    output.write_text(json.dumps(openapi, indent=2))
    print(f"Wrote OpenAPI schema to {output}")


if __name__ == "__main__":
    main()
