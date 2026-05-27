"""Tests for `agent_docs.ingest.fetch` retry behavior."""

from __future__ import annotations

import pytest

from agent_docs.ingest import fetch as fetch_mod


class TestFetchUrlEmptyBodyRetry:
    def test_retries_when_body_empty_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def _fake_http_get(url: str, timeout: int = 30):
            calls.append(url)
            if len(calls) == 1:
                return 200, "text/plain", ""
            return 200, "text/plain", "hello content"

        monkeypatch.setattr(fetch_mod, "http_get", _fake_http_get)
        monkeypatch.setattr(fetch_mod, "time", __import__("time"))

        text, ctype = fetch_mod.fetch_url("https://example.com/page")
        assert text == "hello content"
        assert ctype == "text/plain"
        assert len(calls) == 2

    def test_returns_none_when_body_always_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_http_get(url: str, timeout: int = 30):
            return 200, "text/plain", ""

        monkeypatch.setattr(fetch_mod, "http_get", _fake_http_get)
        monkeypatch.setattr(fetch_mod, "time", __import__("time"))

        text, ctype = fetch_mod.fetch_url("https://example.com/page")
        assert text is None
        assert ctype is None
