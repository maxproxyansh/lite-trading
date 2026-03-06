from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402


def main() -> None:
    output = ROOT / "backend" / "openapi.json"
    output.write_text(json.dumps(app.openapi(), indent=2))
    print(f"Wrote OpenAPI schema to {output}")


if __name__ == "__main__":
    main()
