"""Shared helpers for the test suite."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def scratch_dir(prefix: str) -> str:
    """Create a temporary directory for a test.

    The system temp directory is not writable on every machine, and Python
    then falls back to the current working directory, which would litter the
    repository. The scratch area therefore lives under ``backend/var``.
    """
    base = Path(__file__).resolve().parent.parent / "var" / "test"
    base.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=str(base))


def remove_scratch(path: str) -> None:
    """Remove a scratch directory, ignoring cleanup failures."""
    shutil.rmtree(path, ignore_errors=True)
