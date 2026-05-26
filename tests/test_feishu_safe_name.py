"""Tests for `agent_docs.sinks.feishu.feishu_safe_name`.

Used when titling Feishu documents on import. Must:
- strip filesystem-unsafe characters,
- collapse whitespace,
- remove the `-import` suffix that lark-cli historically appended (see EXPERIENCE.md),
- truncate to a safe length,
- never return empty ("untitled" fallback).
"""

from __future__ import annotations

from agent_docs.core.config import FEISHU_SAFE_NAME_MAX_LEN
from agent_docs.sinks.feishu import feishu_safe_name


class TestFeishuSafeName:
    def test_basic_title(self) -> None:
        assert feishu_safe_name("技能编写最佳实践") == "技能编写最佳实践"

    def test_strips_slashes_and_specials(self) -> None:
        out = feishu_safe_name('a/b\\c:d*e?f"g<h>i|j')
        for ch in '\\/:*?"<>|':
            assert ch not in out

    def test_collapses_whitespace(self) -> None:
        assert feishu_safe_name("  hello    world  \t\n") == "hello world"

    def test_removes_import_suffix(self) -> None:
        assert feishu_safe_name("My Doc-import") == "My Doc"

    def test_removes_import_suffix_case_insensitive(self) -> None:
        assert feishu_safe_name("My Doc-IMPORT") == "My Doc"

    def test_keeps_internal_import(self) -> None:
        # Only the trailing `-import` is stripped, not occurrences inside the title.
        assert feishu_safe_name("How to -import handle") == "How to -import handle"

    def test_empty_input(self) -> None:
        assert feishu_safe_name("") == "untitled"

    def test_only_unsafe_chars(self) -> None:
        # All chars are unsafe and get replaced with _; final is just a string of _.
        out = feishu_safe_name("/\\:*?")
        assert out  # not empty
        assert all(ch in "_" for ch in out)

    def test_truncates_to_max_len(self) -> None:
        long = "x" * (FEISHU_SAFE_NAME_MAX_LEN + 50)
        assert len(feishu_safe_name(long)) == FEISHU_SAFE_NAME_MAX_LEN
