"""Tests for `agent_docs.core.logging.PipelineLogger` secret scrubbing.

PipelineLogger writes to {output_root}/pipeline.log as JSON Lines. It MUST NOT
leak Bearer tokens, OpenAI-style keys, GitHub tokens, URL credential query
params, or common `authorization=` / `app_secret=` assignments coming from
third-party CLI stdout/stderr.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_docs.core.logging import PipelineLogger


@pytest.fixture
def logger(tmp_path: Path) -> PipelineLogger:
    return PipelineLogger(tmp_path)


def _read_log(logger: PipelineLogger) -> dict:
    raw = logger.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1, f"expected 1 log line, got {len(raw)}"
    return json.loads(raw[0])


class TestKeyNameDropping:
    def test_drops_token_key(self, logger: PipelineLogger) -> None:
        logger.log("INFO", "test", folder_token="abc123", path="/safe")
        rec = _read_log(logger)
        assert "folder_token" not in rec
        assert rec["path"] == "/safe"

    def test_drops_secret_keys(self, logger: PipelineLogger) -> None:
        logger.log(
            "INFO",
            "test",
            api_key="sk-test",
            password="p",
            authorization="Bearer abc",
            credential="c",
        )
        rec = _read_log(logger)
        for k in ("api_key", "password", "authorization", "credential"):
            assert k not in rec


class TestValueScrubbing:
    def test_authorization_header_no_double_redaction(self, logger: PipelineLogger) -> None:
        # Regression: when input matches both the `Authorization: Bearer ...`
        # header shape and the bare `Bearer ...` shape, output must collapse
        # to a SINGLE `[REDACTED]` block, not nested redactions.
        logger.log("ERROR", "test", message="Authorization: Bearer sk-ant-AbCdEf1234567890XYZ")
        rec = _read_log(logger)
        assert "sk-ant-AbCdEf1234567890XYZ" not in rec["message"]
        # Exactly one redacted block; no `[REDACTED] [REDACTED]` artefact.
        assert rec["message"].count("[REDACTED]") == 1
        assert "Authorization: [REDACTED]" in rec["message"]

    def test_bare_bearer_still_redacted(self, logger: PipelineLogger) -> None:
        # The HTTP-header-shape pattern must NOT prevent bare `Bearer xxx` from
        # being redacted elsewhere in the same line.
        logger.log("INFO", "test", message="curl -H 'Bearer abc.def.ghi-jklmnop' https://x")
        rec = _read_log(logger)
        assert "abc.def.ghi-jklmnop" not in rec["message"]
        assert "REDACTED" in rec["message"]

    def test_authorization_basic_scheme(self, logger: PipelineLogger) -> None:
        logger.log("ERROR", "test", message="Authorization: Basic dXNlcjpwYXNzd29yZA==")
        rec = _read_log(logger)
        assert "dXNlcjpwYXNzd29yZA==" not in rec["message"]
        assert "Authorization: [REDACTED]" in rec["message"]

    def test_bearer_token_in_message(self, logger: PipelineLogger) -> None:
        logger.log(
            "ERROR",
            "test",
            message="request failed; tried Authorization: Bearer abc.def.ghi-jklmnop",
        )
        rec = _read_log(logger)
        assert "Bearer abc.def.ghi-jklmnop" not in rec["message"]
        assert "REDACTED" in rec["message"]

    def test_openai_sk_key(self, logger: PipelineLogger) -> None:
        logger.log(
            "ERROR",
            "test",
            message="using OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
        )
        rec = _read_log(logger)
        assert "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789" not in rec["message"]
        assert "REDACTED" in rec["message"]

    def test_github_token(self, logger: PipelineLogger) -> None:
        logger.log(
            "ERROR",
            "test",
            message="git push failed: ghp_AbCdEf1234567890AbCdEf1234567890Abcd",
        )
        rec = _read_log(logger)
        assert "ghp_AbCdEf1234567890AbCdEf1234567890Abcd" not in rec["message"]
        assert "REDACTED" in rec["message"]

    def test_url_token_query_param(self, logger: PipelineLogger) -> None:
        logger.log(
            "INFO",
            "test",
            url="https://api.example.com/x?token=abcdef12345&other=ok",
        )
        rec = _read_log(logger)
        assert "abcdef12345" not in rec["url"]
        # Non-secret query params should remain visible.
        assert "other=ok" in rec["url"]

    def test_authorization_assignment_in_value(self, logger: PipelineLogger) -> None:
        logger.log(
            "INFO",
            "test",
            stdout='Sending Authorization="Basic dXNlcjpwYXNz" to server',
        )
        rec = _read_log(logger)
        assert "dXNlcjpwYXNz" not in rec["stdout"]

    def test_app_secret_assignment(self, logger: PipelineLogger) -> None:
        logger.log(
            "ERROR",
            "test",
            message="app_secret=cli_a123b456c789d012 sent",
        )
        rec = _read_log(logger)
        assert "cli_a123b456c789d012" not in rec["message"]

    def test_non_secret_value_unchanged(self, logger: PipelineLogger) -> None:
        logger.log("INFO", "test", message="batch-001 fetched 5 items")
        rec = _read_log(logger)
        assert rec["message"] == "batch-001 fetched 5 items"

    def test_nested_dict_value_scrubbed(self, logger: PipelineLogger) -> None:
        logger.log(
            "ERROR",
            "test",
            details={"stdout": "sent Bearer leak_token_xyz"},
        )
        rec = _read_log(logger)
        assert "leak_token_xyz" not in json.dumps(rec)

    def test_list_value_scrubbed(self, logger: PipelineLogger) -> None:
        logger.log("ERROR", "test", commands=["echo Bearer secret123", "ls"])
        rec = _read_log(logger)
        assert "Bearer secret123" not in json.dumps(rec)


class TestLogStructure:
    def test_has_required_fields(self, logger: PipelineLogger) -> None:
        logger.log("INFO", "crawl", batch_id="batch-001", message="ok")
        rec = _read_log(logger)
        assert rec["level"] == "INFO"
        assert rec["stage"] == "crawl"
        assert "timestamp_utc" in rec
        assert rec["batch_id"] == "batch-001"

    def test_append_only(self, logger: PipelineLogger) -> None:
        logger.log("INFO", "stage1", message="a")
        logger.log("INFO", "stage2", message="b")
        lines = logger.log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
