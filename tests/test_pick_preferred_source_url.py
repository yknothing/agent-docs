"""Tests for `agent_docs.ingest.translate.pick_preferred_source_url`.

Chinese-first source selection: given an EN URL, probe `/zh-CN/` then `/zh/`.
Network is mocked; we only verify the URL transformation logic + decision tree.
"""

from __future__ import annotations

import pytest

from agent_docs.ingest import translate as translate_mod


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def _fake(url: str) -> bool:
        calls.append(url)
        return False

    monkeypatch.setattr(translate_mod, "test_source_available", _fake)
    return calls


@pytest.fixture
def zh_available(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def _fake(url: str) -> bool:
        calls.append(url)
        return "/zh-CN/" in url

    monkeypatch.setattr(translate_mod, "test_source_available", _fake)
    return calls


class TestPickPreferredSourceUrl:
    def test_empty_url(self, no_network: list[str]) -> None:
        out, has_zh = translate_mod.pick_preferred_source_url("")
        assert out == ""
        assert has_zh is False
        assert no_network == []  # no probes made

    def test_url_already_zh_cn(self, no_network: list[str]) -> None:
        url = "https://platform.claude.com/docs/zh-CN/home"
        out, has_zh = translate_mod.pick_preferred_source_url(url)
        assert out == url
        assert has_zh is True
        assert no_network == []  # no probes; already zh

    def test_url_already_zh(self, no_network: list[str]) -> None:
        url = "https://platform.claude.com/docs/zh/home"
        out, has_zh = translate_mod.pick_preferred_source_url(url)
        assert out == url
        assert has_zh is True

    def test_url_no_locale_marker(self, no_network: list[str]) -> None:
        # No `/en/` and no `/zh.../` => return as-is, no probe.
        url = "https://platform.claude.com/llms.txt"
        out, has_zh = translate_mod.pick_preferred_source_url(url)
        assert out == url
        assert has_zh is False
        assert no_network == []

    def test_url_with_en_zh_cn_available(self, zh_available: list[str]) -> None:
        url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills"
        out, has_zh = translate_mod.pick_preferred_source_url(url)
        assert has_zh is True
        assert "/zh-CN/" in out
        assert out == "https://platform.claude.com/docs/zh-CN/agents-and-tools/agent-skills"

    def test_url_with_en_no_zh_available(self, no_network: list[str]) -> None:
        url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills"
        out, has_zh = translate_mod.pick_preferred_source_url(url)
        assert has_zh is False
        assert out == url  # falls back to original
        # Two probes: /zh-CN/ then /zh/
        assert len(no_network) == 2
        assert any("/zh-CN/" in u for u in no_network)
        assert any("/zh/" in u for u in no_network)
