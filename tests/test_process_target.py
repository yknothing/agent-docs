"""Tests for `agent_docs.ingest.process.process_target` Chinese-first selection."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from agent_docs.core.config import QA_ERR_TRANSLATE_MISSING
from agent_docs.ingest import process as process_mod
from agent_docs.ingest import translate as translate_mod
from agent_docs.qa.gates import run_content_qa_item

ZH_MD = "# 标题\n\n" + ("中文内容足够长。" * 10)
EN_MD = "# Agents\n\n" + ("English technical content about agents and tools. " * 8)
EN_URL = "https://example.com/docs/article.md"


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


def _english_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cfg: argparse.Namespace):
    def _fake_fetch(url: str, timeout: int = 30):
        assert url == EN_URL
        return EN_MD, "text/markdown"

    monkeypatch.setattr(process_mod, "fetch_url", _fake_fetch)
    monkeypatch.delenv("LANGCRAFT_CMD", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    batch_dir = tmp_path / "batch-001"
    batch_dir.mkdir()
    return process_mod.process_target(
        {"source_url": EN_URL, "source_type": "platform_docs"},
        cfg,
        batch_dir,
        1,
    )


class TestTranslateMode:
    def test_off_accepts_english_without_translate_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = argparse.Namespace(translate=True, translate_mode="off", translate_timeout=5)
        result = _english_page(tmp_path, monkeypatch, cfg)
        final_text = Path(str(result["final_path"])).read_text(encoding="utf-8")

        assert result["source_language"] == "en"
        assert result["need_translate"] is False
        assert result["final_language"] == "en"
        assert str(result["translator"]).startswith("skipped")
        errors = run_content_qa_item(result, final_text)
        assert not any(error.startswith(f"{QA_ERR_TRANSLATE_MISSING}:") for error in errors)

    def test_auto_without_translator_still_reports_translate_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = argparse.Namespace(translate=True, translate_mode="auto", translate_timeout=5)
        result = _english_page(tmp_path, monkeypatch, cfg)
        final_text = Path(str(result["final_path"])).read_text(encoding="utf-8")

        assert result["need_translate"] is True
        assert result["final_language"] == "en"
        errors = run_content_qa_item(result, final_text)
        assert any(error.startswith(f"{QA_ERR_TRANSLATE_MISSING}:") for error in errors)
