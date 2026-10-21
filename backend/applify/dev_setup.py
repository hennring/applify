"""Start the dev database and apply migrations: python -m applify.dev_setup"""

import subprocess
from pathlib import Path

from alembic.config import main as alembic

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait", "db"], cwd=BACKEND_DIR.parent, check=True
    )
    alembic(argv=["-c", str(BACKEND_DIR / "alembic.ini"), "upgrade", "head"])


if __name__ == "__main__":
    main()
