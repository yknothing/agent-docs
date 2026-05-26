"""Wraps the inline `run_feishu_path_self_test` as a proper pytest test.

Keeps the legacy `python scripts/anthropic_content_pipeline.py --self-test-feishu-paths`
entry point working while exposing the same checks to the CI pytest invocation.
"""

from __future__ import annotations

from agent_docs.sinks import run_feishu_path_self_test


def test_feishu_path_self_test_passes() -> None:
    # The function uses assert statements internally; if any fails it raises.
    run_feishu_path_self_test()
