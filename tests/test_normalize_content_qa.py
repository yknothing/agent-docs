"""Tests for content QA helpers in `agent_docs.ingest.normalize`."""

from __future__ import annotations

from agent_docs.core.config import CHINESE_RATIO_THRESHOLD, MIN_VISIBLE_CONTENT_LEN
from agent_docs.ingest.normalize import chinese_ratio, is_content_too_short, is_not_found_text


class TestChineseRatio:
    def test_empty_returns_zero(self) -> None:
        assert chinese_ratio("") == 0.0

    def test_pure_english_returns_zero(self) -> None:
        assert chinese_ratio("Hello world, no CJK here.") == 0.0

    def test_below_threshold(self) -> None:
        # One CJK char in 400 ASCII chars => 0.0025 < 0.005
        text = "中" + ("a" * 399)
        ratio = chinese_ratio(text)
        assert ratio < CHINESE_RATIO_THRESHOLD
        assert ratio == 1 / 400

    def test_at_threshold_boundary(self) -> None:
        # Exactly at threshold: 1 CJK in 200 chars => 0.005
        text = "中" + ("x" * 199)
        assert chinese_ratio(text) == CHINESE_RATIO_THRESHOLD

    def test_above_threshold(self) -> None:
        text = "中文内容" * 20
        assert chinese_ratio(text) > CHINESE_RATIO_THRESHOLD

    def test_mixed_content(self) -> None:
        text = "# Title\n\n" + ("English paragraph. " * 5) + ("中文段落。" * 5)
        assert chinese_ratio(text) > CHINESE_RATIO_THRESHOLD


class TestIsContentTooShort:
    def _long_enough_body(self) -> str:
        filler = "x" * MIN_VISIBLE_CONTENT_LEN
        return f"# Heading\n\n{filler}"

    def test_long_enough_not_too_short(self) -> None:
        assert is_content_too_short(self._long_enough_body()) is False

    def test_empty_is_too_short(self) -> None:
        assert is_content_too_short("") is True

    def test_whitespace_and_markdown_only_is_too_short(self) -> None:
        assert is_content_too_short("# Title\n\n---\n\n| a | b |\n| - | - |") is True

    def test_just_below_min_visible_len(self) -> None:
        body = "a" * (MIN_VISIBLE_CONTENT_LEN - 2)
        assert is_content_too_short(f"# H\n\n{body}") is True

    def test_at_min_visible_len(self) -> None:
        body = "a" * MIN_VISIBLE_CONTENT_LEN
        assert is_content_too_short(f"# H\n\n{body}") is False


class TestIsNotFoundText:
    def test_empty_text_is_not_found(self) -> None:
        assert is_not_found_text("") is True

    def test_title_with_404(self) -> None:
        assert is_not_found_text("Some body", title="Page 404 Error") is True

    def test_title_with_not_found(self) -> None:
        assert is_not_found_text("Some body", title="Document Not Found") is True

    def test_normal_title_is_found(self) -> None:
        assert is_not_found_text("# Agent Skills\n\nContent here.", title="Agent Skills") is False

    def test_extracts_title_from_markdown_when_none(self) -> None:
        assert is_not_found_text("# 404 Not Found\n\nOops.") is True

    def test_no_title_in_text_returns_false(self) -> None:
        assert is_not_found_text("plain text without heading") is False
