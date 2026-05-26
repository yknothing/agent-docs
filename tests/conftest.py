"""Shared pytest fixtures for agent-docs unit tests.

Unit tests are network-free by default. Anything requiring real network access
must be marked `@pytest.mark.network` and is excluded from the default run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `agent_docs` importable when the package is not pip-installed (e.g., CI
# without `pip install -e .`). Tests run from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip network-marked tests unless `-m network` is passed explicitly."""
    marker_expr = config.getoption("-m") or ""
    if "network" in marker_expr:
        return
    skip_marker = pytest.mark.skip(reason="network test (run with `pytest -m network`)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_marker)
