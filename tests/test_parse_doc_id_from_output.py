"""Tests for `agent_docs.sinks.feishu.parse_doc_id_from_output`.

This function consumes raw `lark-cli` subprocess output (which has historically
been unstable: stderr-after-JSON, nested data, plain text). It is the single
point that turns a successful upload into a doc_id we can verify and link to.
"""

from __future__ import annotations

import json

from agent_docs.sinks.feishu import parse_doc_id_from_output, parse_lark_cli_json


class TestParseDocId:
    def test_pure_json_with_token(self) -> None:
        out = json.dumps({"ok": True, "data": {"token": "docxAbc123XYZ"}})
        assert parse_doc_id_from_output(out) == "docxAbc123XYZ"

    def test_pure_json_with_document_id(self) -> None:
        out = json.dumps({"ok": True, "data": {"document_id": "doc-XYZ"}})
        assert parse_doc_id_from_output(out) == "doc-XYZ"

    def test_nested_document_object(self) -> None:
        out = json.dumps(
            {"ok": True, "data": {"document": {"document_id": "nested-id-001"}}}
        )
        assert parse_doc_id_from_output(out) == "nested-id-001"

    def test_double_nested_data(self) -> None:
        out = json.dumps({"ok": True, "data": {"data": {"token": "deep-token"}}})
        assert parse_doc_id_from_output(out) == "deep-token"

    def test_json_followed_by_stderr(self) -> None:
        # Real-world: lark-cli sometimes appends "Creating folder ok" stderr
        # after the JSON body on stdout. raw_decode must still find the first
        # JSON object.
        out = json.dumps({"ok": True, "data": {"token": "abc-tok"}}) + "\nCreating folder ok\n"
        assert parse_doc_id_from_output(out) == "abc-tok"

    def test_plain_text_unquoted_value(self) -> None:
        # `document_id[:=]\s*([A-Za-z0-9_-]+)` matches plain unquoted tokens.
        out = "INFO: created document_id: plaintextid_77"
        assert parse_doc_id_from_output(out) == "plaintextid_77"

    def test_url_fallback(self) -> None:
        out = "created at https://my.feishu.cn/docx/abc123_xyz"
        result = parse_doc_id_from_output(out)
        assert result is not None
        assert "docx" in result

    def test_empty_input(self) -> None:
        assert parse_doc_id_from_output("") is None

    def test_garbage_input(self) -> None:
        assert parse_doc_id_from_output("<<not even close>>") is None


class TestParseLarkCliJson:
    def test_basic(self) -> None:
        payload = parse_lark_cli_json('{"ok":true,"data":{}}')
        assert payload is not None
        assert payload["ok"] is True

    def test_json_with_trailing_stderr(self) -> None:
        # Regression: see EXPERIENCE.md 2026-05-21 "lark-cli JSON 解析失败".
        payload = parse_lark_cli_json('{"ok":true,"data":{"folder_token":"tok"}}\nCreating folder...\n')
        assert payload is not None
        assert payload["data"]["folder_token"] == "tok"

    def test_no_json(self) -> None:
        assert parse_lark_cli_json("plain text") is None

    def test_empty(self) -> None:
        assert parse_lark_cli_json("") is None
