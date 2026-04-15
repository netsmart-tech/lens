"""Dump the FastAPI OpenAPI schema to backend/openapi.json.

Used by the frontend's client generator. Run via `make openapi`.
"""

from __future__ import annotations

import json
from pathlib import Path

from lens.main import app


def main() -> None:
    out = Path("openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
