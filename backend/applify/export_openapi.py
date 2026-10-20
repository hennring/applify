"""Write the OpenAPI schema for the frontend types: python -m applify.export_openapi"""

import json
import sys
from pathlib import Path

from applify.main import create_app


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    target.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
