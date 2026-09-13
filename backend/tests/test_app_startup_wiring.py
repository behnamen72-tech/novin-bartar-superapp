import os
import subprocess
import sys
from pathlib import Path


def test_real_app_import_registers_organization_listener() -> None:
    backend_dir = Path(__file__).resolve().parents[1]

    script = r"""
from sqlalchemy import event
from sqlalchemy.orm import Session

import app.main
from app.core.organization.events import validate_organization_hierarchy_before_flush

assert event.contains(
    Session,
    "before_flush",
    validate_organization_hierarchy_before_flush,
), "Organization hierarchy listener was not registered by real app startup"
"""

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    env["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
