"""Tests for `agent_docs.ingest.normalize.parse_frontmatter`.

This is a hand-rolled YAML-subset parser. Tests pin down what it DOES support
(flat key:value, quoted strings, bool, int/float) and what it KNOWN-DOESN'T
support (multi-line values, lists, nested mappings). Limitations are tracked
in ARCHITECTURE.md Known Limitations.
"""

from __future__ import annotations

import pytest

from agent_docs.ingest.normalize import parse_frontmatter, strip_frontmatter


class TestParseFrontmatterSupported:
    def test_no_frontmatter(self) -> None:
        meta, body = parse_frontmatter("hello world")
        assert meta == {}
        assert body == "hello world"

    def test_simple_key_value(self) -> None:
        text = '---\ntitle: "Hello"\n---\nbody'
        meta, body = parse_frontmatter(text)
        assert meta == {"title": "Hello"}
        assert body == "body"

    def test_bool_values(self) -> None:
        text = "---\npublished: true\ndraft: false\n---\nbody"
        meta, _ = parse_frontmatter(text)
        assert meta == {"published": True, "draft": False}

    def test_int_and_float(self) -> None:
        text = "---\nyear: 2026\nratio: 0.42\n---\nbody"
        meta, _ = parse_frontmatter(text)
        assert meta["year"] == 2026
        assert meta["ratio"] == 0.42

    def test_quoted_string_with_escaped_quote(self) -> None:
        text = '---\ntitle: "Say \\"hi\\""\n---\nbody'
        meta, _ = parse_frontmatter(text)
        assert meta["title"] == 'Say "hi"'

    def test_value_with_colon_unquoted(self) -> None:
        # `partition(':', 1)` keeps the rest of the colons in the value.
        text = "---\ntitle: Hello: world\n---\nbody"
        meta, _ = parse_frontmatter(text)
        assert meta["title"] == "Hello: world"

    def test_iso_date_passes_through_as_string(self) -> None:
        text = '---\ndate: "2026-05-22T00:00:00+00:00"\n---\nbody'
        meta, _ = parse_frontmatter(text)
        assert meta["date"] == "2026-05-22T00:00:00+00:00"

    def test_strip_frontmatter_helper(self) -> None:
        assert strip_frontmatter("---\nk: v\n---\nbody") == "body"
        assert strip_frontmatter("no fm") == "no fm"


class TestParseFrontmatterKnownLimitations:
    """Document current behavior; flip to passing if the parser is upgraded."""

    def test_list_value_not_parsed_as_list(self) -> None:
        # Hand-rolled parser sees `- foo` on its own line as malformed (no `:`).
        text = "---\ntags:\n  - a\n  - b\n---\nbody"
        meta, _ = parse_frontmatter(text)
        # current behavior: `tags` value is empty string; the bullets are ignored.
        assert meta["tags"] == ""

    @pytest.mark.xfail(
        reason="Hand-rolled parser does not support nested mappings",
        strict=True,
    )
    def test_nested_mapping_not_supported(self) -> None:
        text = "---\nauthor:\n  name: ada\n---\nbody"
        meta, _ = parse_frontmatter(text)
        # If we ever upgrade to PyYAML, this should pass.
        assert isinstance(meta["author"], dict)
