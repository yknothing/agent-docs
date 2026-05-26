"""Tests for `agent_docs.sinks.feishu.feishu_folder_segments` URL mapping.

Covers every known vendor URL family and both root modes (agent-docs-folder /
parent). These mappings are user-facing (Feishu directory layout) and must
remain stable; this suite is the regression net.
"""

from __future__ import annotations

import argparse

import pytest

from agent_docs.sinks.feishu import (
    feishu_folder_segments,
    feishu_full_folder_path,
)


def _cfg(mode: str = "agent-docs-folder") -> argparse.Namespace:
    return argparse.Namespace(feishu_doc_root_mode=mode)


BASE = ["anthropic-docs", "Anthropic"]


class TestPlatformDocs:
    def test_agent_skills_best_practices(self) -> None:
        url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
        segs = feishu_folder_segments(url, "platform_docs", _cfg())
        assert segs == BASE + ["Developer-docs", "agents-and-tools", "agent-skills"]

    def test_strips_locale_zh_cn(self) -> None:
        url = "https://platform.claude.com/docs/zh-CN/agents-and-tools/agent-skills/best-practices"
        segs = feishu_folder_segments(url, "platform_docs", _cfg())
        assert "zh-CN" not in segs
        assert segs == BASE + ["Developer-docs", "agents-and-tools", "agent-skills"]

    def test_single_path_segment(self) -> None:
        url = "https://platform.claude.com/docs/en/home"
        segs = feishu_folder_segments(url, "platform_docs", _cfg())
        # parent of last segment is empty, so only Developer-docs is appended.
        assert segs == BASE + ["Developer-docs"]


class TestCodeDocs:
    def test_claude_code_hooks(self) -> None:
        url = "https://code.claude.com/docs/en/hooks"
        segs = feishu_folder_segments(url, "claude_code_docs", _cfg())
        assert segs == BASE + ["Developer-docs", "Claude Code"]

    def test_nested_path(self) -> None:
        url = "https://code.claude.com/docs/en/agents/multi-agent"
        segs = feishu_folder_segments(url, "claude_code_docs", _cfg())
        assert segs == BASE + ["Developer-docs", "Claude Code", "agents"]


class TestAnthropicComCategories:
    @pytest.mark.parametrize(
        "prefix,expected_category",
        [
            ("learn", "Anthropic Academy"),
            ("engineering", "Engineering"),
            ("news", "News"),
            ("research", "Research"),
            ("economic-futures", "Economic Futures"),
            ("system-cards", "System Cards"),
        ],
    )
    def test_category_mapping(self, prefix: str, expected_category: str) -> None:
        url = f"https://www.anthropic.com/{prefix}/some-article"
        segs = feishu_folder_segments(url, "anthropic_news", _cfg())
        assert segs == BASE + [expected_category]

    def test_unknown_prefix_falls_back_to_segment_name(self) -> None:
        url = "https://www.anthropic.com/whatever/post"
        segs = feishu_folder_segments(url, "", _cfg())
        assert segs == BASE + ["whatever"]

    def test_root_path(self) -> None:
        url = "https://www.anthropic.com/"
        segs = feishu_folder_segments(url, "", _cfg())
        assert segs == BASE + ["Other"]


class TestClaudeCom:
    def test_blog_post(self) -> None:
        url = "https://claude.com/blog/some-post"
        segs = feishu_folder_segments(url, "", _cfg())
        assert "Claude" in segs and "Blog" in segs

    def test_tutorials(self) -> None:
        url = "https://claude.com/resources/tutorials/build-an-agent"
        segs = feishu_folder_segments(url, "", _cfg())
        assert segs[-1] == "Tutorials" or "Tutorials" in segs

    def test_use_cases(self) -> None:
        url = "https://claude.com/resources/use-cases/customer-support"
        segs = feishu_folder_segments(url, "", _cfg())
        assert "User Cases" in segs

    def test_courses_skipped(self) -> None:
        url = "https://claude.com/resources/courses/some-course"
        segs = feishu_folder_segments(url, "", _cfg())
        assert segs == [], "courses path must be empty per FEISHU_EXCLUDED_URL_PATHS"

    def test_unknown_falls_back_to_claude_other(self) -> None:
        url = "https://claude.com/something-else"
        segs = feishu_folder_segments(url, "", _cfg())
        assert segs == BASE + ["Claude", "Other"]


class TestRootMode:
    def test_full_path_agent_docs_folder_mode(self) -> None:
        url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills"
        segs = feishu_folder_segments(url, "platform_docs", _cfg("agent-docs-folder"))
        full = feishu_full_folder_path(segs, _cfg("agent-docs-folder"))
        assert full.startswith("agent-docs/")
        assert full == "agent-docs/anthropic-docs/Anthropic/Developer-docs/agents-and-tools"

    def test_full_path_parent_mode(self) -> None:
        url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills"
        segs = feishu_folder_segments(url, "platform_docs", _cfg("parent"))
        full = feishu_full_folder_path(segs, _cfg("parent"))
        # In parent mode the segments themselves start with agent-docs/.
        assert segs[0] == "agent-docs"
        assert full.startswith("agent-docs/")

    def test_empty_segments(self) -> None:
        assert feishu_full_folder_path([], _cfg()) == ""


class TestSegmentSanitization:
    def test_strips_unsafe_characters(self) -> None:
        # Path segments must not leak filesystem-unsafe characters into Feishu mkdir.
        url = "https://platform.claude.com/docs/en/agents/foo:bar*baz/leaf"
        segs = feishu_folder_segments(url, "platform_docs", _cfg())
        for s in segs:
            for ch in '\\/:*?"<>|':
                assert ch not in s, f"unsafe char {ch!r} found in segment {s!r}"
