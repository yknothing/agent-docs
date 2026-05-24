#!/usr/bin/env python3
"""Compatibility wrapper for Anthropic Stage 1 pipeline CLI."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_docs.cli.anthropic import main  # noqa: E402
from agent_docs.sinks import run_feishu_path_self_test  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test-feishu-paths":
        run_feishu_path_self_test()
        print("[OK] feishu path self-test passed")
    else:
        main()
