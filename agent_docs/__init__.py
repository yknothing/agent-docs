"""Deterministic tools for the agent-docs source library pipeline.

Preferred installation::

    pip install -e ".[dev]"

For backward compatibility with existing npm scripts,
``scripts/anthropic_content_pipeline.py`` still injects the repository root
onto ``sys.path`` so the wrapper works without ``pip install``.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
