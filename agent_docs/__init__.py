"""Deterministic tools for the agent-docs source library pipeline."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    """Insert repository root on sys.path so `agent_docs` imports work without install."""
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


ensure_repo_root_on_path()
