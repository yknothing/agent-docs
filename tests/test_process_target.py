"""Tests for `agent_docs.ingest.process.process_target` Chinese-first selection."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from agent_docs.ingest import process as process_mod
from agent_docs.ingest import translate as translate_mod

ZH_MD = "# 标题\n\n" + ("中文内容足够长。" * 10)


class TestProcessTargetChineseFirst:
    def test_en_platform_url_probes_and_selects_zh_cn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        en_url = (
            "https://platform.claude.com/docs/en/agents-and-tools/"
            "agent-skills/best-practices.md"
        )
        zh_url = en_url.replace("/en/", "/zh-CN/")
        probes: list[str] = []

        def _fake_probe(url: str) -> bool:
            probes.append(url)
            return "/zh-CN/" in url

        def _fake_fetch(url: str, timeout: int = 30):
            if url == zh_url:
                return ZH_MD, "text/markdown"
            return None, None

        monkeypatch.setattr(translate_mod, "test_source_available", _fake_probe)
        monkeypatch.setattr(process_mod, "fetch_url", _fake_fetch)

        batch_dir = tmp_path / "batch-001"
        batch_dir.mkdir()
        cfg = argparse.Namespace(translate=False)

        result = process_mod.process_target(
            {"source_url": en_url, "source_type": "platform_docs"},
            cfg,
            batch_dir,
            1,
        )

        assert result["has_zh_version"] is True
        assert result["selected_url"] == zh_url
        assert result["source_language"] == "zh"
        assert any("/zh-CN/" in u for u in probes)
