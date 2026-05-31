"""Tests for per-item QA gates in `agent_docs.qa.gates`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from agent_docs.core.config import (
    CRAWL_STATUS_FETCHED,
    CRAWL_STATUS_FAILED_FETCH,
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_OK,
    QA_ERR_BAD_IMAGE_COUNT_SOURCE,
    QA_ERR_BAD_TABLE_COUNT_SOURCE,
    QA_ERR_EMPTY_OR_TOO_SHORT,
    QA_ERR_HEADING_COUNT_DECREASE,
    QA_ERR_IMAGE_COUNT_DECREASE,
    QA_ERR_IMAGE_DOWNLOAD_FAILED,
    QA_ERR_IMAGE_FILE_MISSING,
    QA_ERR_IMAGE_NOT_LOCALIZED,
    QA_ERR_LINK_COUNT_DECREASE,
    QA_ERR_NOT_FETCHED,
    QA_ERR_NOT_FOUND_OUTPUT,
    QA_ERR_TABLE_COUNT_DECREASE,
    QA_ERR_TRANSLATE_MISSING,
    QA_ERR_ZH_LANGUAGE_CHECK,
)
from agent_docs.qa.gates import run_content_qa_item, run_technical_qa_item

SOURCE_URL = "https://platform.claude.com/docs/en/test-page"


def _write_pair(tmp_path: Path, *, source: str, final: str) -> tuple[Path, Path]:
    batch = tmp_path / "batch-001" / "001-test"
    batch.mkdir(parents=True)
    src_path = batch / "source.md"
    out_path = batch / "final.md"
    src_path.write_text(source, encoding="utf-8")
    out_path.write_text(final, encoding="utf-8")
    return src_path, out_path


def _base_item(src_path: Path, out_path: Path, **overrides: Any) -> Dict[str, object]:
    item: Dict[str, object] = {
        "source_url": SOURCE_URL,
        "source_path": str(src_path),
        "final_path": str(out_path),
        "status": CRAWL_STATUS_FETCHED,
        "title": "Test Document",
        "image_count_source": 0,
        "image_count_output": 0,
        "table_count_source": 0,
        "table_count_output": 0,
        "heading_count_source": 1,
        "heading_count_output": 1,
        "link_count_source": 0,
        "link_count_output": 0,
        "images": [],
        "need_translate": False,
        "final_language": "zh",
    }
    item.update(overrides)
    return item


def _long_zh_body(prefix: str = "中文正文内容足够长。") -> str:
    return prefix * 15


class TestRunTechnicalQaItem:
    def test_pass_case(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        item = _base_item(src_path, out_path)
        errors, deltas = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert errors == []
        assert deltas["image_count_delta"] == 0

    def test_not_fetched(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{_long_zh_body()}",
            final=f"# Test\n\n{_long_zh_body()}",
        )
        item = _base_item(src_path, out_path, status=CRAWL_STATUS_FAILED_FETCH)
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_NOT_FETCHED}:") for e in errors)

    def test_missing_files_returns_early_without_structure_checks(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{_long_zh_body()}",
            final=f"# Test\n\n{_long_zh_body()}",
        )
        out_path.unlink()
        item = _base_item(src_path, out_path)
        errors, deltas = run_technical_qa_item(item, "")
        assert errors == []
        assert deltas["image_count_delta"] == 0

    def test_empty_or_too_short(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(tmp_path, source="# Test\n\nshort", final="# Test\n\nshort")
        item = _base_item(src_path, out_path)
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_EMPTY_OR_TOO_SHORT}:") for e in errors)

    def test_not_found_output(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# 404 Not Found\n\n{body}",
            final=f"# 404 Not Found\n\n{body}",
        )
        item = _base_item(src_path, out_path, title="404 Not Found")
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_NOT_FOUND_OUTPUT}:") for e in errors)

    def test_bad_image_count_source(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{_long_zh_body()}",
            final=f"# Test\n\n{_long_zh_body()}",
        )
        item = _base_item(src_path, out_path, image_count_source="bad")
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_BAD_IMAGE_COUNT_SOURCE}:") for e in errors)

    def test_bad_table_count_source(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{_long_zh_body()}",
            final=f"# Test\n\n{_long_zh_body()}",
        )
        item = _base_item(src_path, out_path, table_count_source=None)
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_BAD_TABLE_COUNT_SOURCE}:") for e in errors)

    @pytest.mark.parametrize(
        ("field", "code"),
        [
            ("image_count_source", QA_ERR_IMAGE_COUNT_DECREASE),
            ("table_count_source", QA_ERR_TABLE_COUNT_DECREASE),
            ("heading_count_source", QA_ERR_HEADING_COUNT_DECREASE),
            ("link_count_source", QA_ERR_LINK_COUNT_DECREASE),
        ],
    )
    def test_count_decrease_errors(self, tmp_path: Path, field: str, code: str) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        item = _base_item(src_path, out_path, **{field: 2, field.replace("source", "output"): 1})
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{code}:") for e in errors)

    def test_image_download_failed(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        item = _base_item(
            src_path,
            out_path,
            images=[{"source": "https://example.com/a.png", "file": "media/a.png", "status": IMAGE_STATUS_FAILED}],
        )
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_IMAGE_DOWNLOAD_FAILED}:") for e in errors)

    def test_image_file_missing(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        missing = src_path.parent / "media" / "missing.png"
        item = _base_item(
            src_path,
            out_path,
            images=[{"source": "https://example.com/missing.png", "file": str(missing), "status": IMAGE_STATUS_OK}],
        )
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_IMAGE_FILE_MISSING}:") for e in errors)

    def test_image_not_localized(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        media_dir = src_path.parent / "media"
        media_dir.mkdir()
        image_file = media_dir / "orphan.png"
        image_file.write_bytes(b"png")
        item = _base_item(
            src_path,
            out_path,
            images=[{"source": "https://example.com/orphan.png", "file": str(image_file), "status": IMAGE_STATUS_OK}],
        )
        errors, _ = run_technical_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_IMAGE_NOT_LOCALIZED}:") for e in errors)


class TestRunContentQaItem:
    def test_pass_zh_content(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        item = _base_item(src_path, out_path, final_language="zh")
        errors = run_content_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert errors == []

    def test_translate_missing(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_pair(
            tmp_path,
            source=f"# Test\n\n{body}",
            final=f"# Test\n\n{body}",
        )
        item = _base_item(src_path, out_path, need_translate=True, final_language="en")
        errors = run_content_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_TRANSLATE_MISSING}:") for e in errors)

    def test_zh_language_check_failed(self, tmp_path: Path) -> None:
        src_path, out_path = _write_pair(
            tmp_path,
            source="# Test\n\nEnglish only content without Chinese characters.",
            final="# Test\n\nEnglish only content without Chinese characters.",
        )
        item = _base_item(src_path, out_path, final_language="zh")
        errors = run_content_qa_item(item, out_path.read_text(encoding="utf-8"))
        assert any(e.startswith(f"{QA_ERR_ZH_LANGUAGE_CHECK}:") for e in errors)
