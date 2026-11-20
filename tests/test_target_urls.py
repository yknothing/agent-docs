"""Fail-closed handling for ``--target-url`` values missing from discovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from agent_docs.cli.anthropic import main, parse_args
from agent_docs.ingest.discover import UndiscoveredTargetURLs, build_targets


def _cfg(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "include_platform_docs": True,
        "include_code_docs": False,
        "include_news": True,
        "allowed_news_prefixes": ["news", "research"],
        "target_urls": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _patch_discovery(monkeypatch: pytest.MonkeyPatch, docs: list[str], news: list[str]) -> None:
    monkeypatch.setattr(
        "agent_docs.ingest.discover.extract_links_from_llms",
        lambda url: list(docs),
    )
    monkeypatch.setattr(
        "agent_docs.ingest.discover.discover_news_urls",
        lambda **kwargs: list(news),
    )


class TestBuildTargetsFailClosed:
    def test_missing_url_raises_and_lists_every_gap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        known = "https://www.anthropic.com/news/known-article"
        missing_a = "https://www.anthropic.com/engineering/not-in-sitemap"
        missing_b = "https://www.anthropic.com/engineering/also-missing"
        _patch_discovery(monkeypatch, docs=[], news=[known])

        with pytest.raises(UndiscoveredTargetURLs) as exc:
            build_targets(
                _cfg(
                    target_urls=[known, missing_a, missing_a, missing_b],
                )
            )

        assert exc.value.missing == [missing_a, missing_b]

    def test_requested_urls_are_kept_and_others_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keep = "https://www.anthropic.com/research/building-effective-agents"
        extra = "https://www.anthropic.com/news/other"
        _patch_discovery(monkeypatch, docs=[], news=[extra, keep])

        targets = build_targets(_cfg(include_platform_docs=False, target_urls=[keep]))

        assert [item["source_url"] for item in targets] == [keep]

    def test_canonical_form_matches_without_failing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        discovered = "https://www.anthropic.com/research/building-effective-agents"
        _patch_discovery(monkeypatch, docs=[], news=[discovered])

        targets = build_targets(
            _cfg(
                include_platform_docs=False,
                target_urls=["HTTPS://WWW.ANTHROPIC.COM/research/building-effective-agents/"],
            )
        )

        assert [item["source_url"] for item in targets] == [discovered]


class TestCliTargetUrlFailure:
    def test_main_exits_nonzero_and_names_the_url(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        missing = "https://www.anthropic.com/engineering/building-effective-agents"
        _patch_discovery(
            monkeypatch,
            docs=["https://platform.claude.com/docs/en/known.md"],
            news=["https://www.anthropic.com/news/known-article"],
        )

        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "--target-url",
                    missing,
                    "--translate-mode",
                    "off",
                    "--output-root",
                    str(tmp_path),
                    "--no-include-code-docs",
                ]
            )

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert f"[ERROR] target_url_not_discovered: {missing}" in captured.err
        report = json.loads(captured.out)
        assert report["overall_status"] == "FAIL"
        assert report["target_count"] == 0
        assert report["missing_target_urls"] == [missing]
        assert not (tmp_path / "discover.json").exists()
        assert list(tmp_path.glob("batch-*")) == []

    def test_allow_failures_does_not_hide_a_missing_url(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        _patch_discovery(monkeypatch, docs=[], news=[])

        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "--discover-only",
                    "--allow-failures",
                    "--target-url",
                    "https://www.anthropic.com/news/missing",
                    "--output-root",
                    str(tmp_path),
                    "--no-include-platform-docs",
                    "--no-include-code-docs",
                ]
            )

        assert exc.value.code == 1
        report = json.loads(capsys.readouterr().out)
        assert report["overall_status"] == "FAIL"
        assert "https://www.anthropic.com/news/missing" in report["missing_target_urls"]

    def test_translate_mode_off_disables_translate_flag(self) -> None:
        cfg = parse_args(["--translate-mode", "off"])
        assert cfg.translate_mode == "off"
        assert cfg.translate is False

        cfg_auto = parse_args(["--translate-mode", "auto"])
        assert cfg_auto.translate is True
