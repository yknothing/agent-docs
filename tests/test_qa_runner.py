"""Tests for batch QA runner in `agent_docs.qa.runner`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent_docs.core.config import (
    CRAWL_STATUS_FETCHED,
    CRAWL_STATUS_FAILED_FETCH,
    QA_STATUS_FAIL,
    QA_STATUS_PASS,
    QA_STATUS_SKIPPED,
)
from agent_docs.core.logging import PipelineLogger
from agent_docs.qa.runner import run_qa

SOURCE_URL = "https://platform.claude.com/docs/en/runner-test"


def _write_item_files(tmp_path: Path, slug: str, *, source: str, final: str) -> tuple[Path, Path]:
    item_dir = tmp_path / "batch-001" / slug
    item_dir.mkdir(parents=True)
    src_path = item_dir / "source.md"
    out_path = item_dir / "final.md"
    src_path.write_text(source, encoding="utf-8")
    out_path.write_text(final, encoding="utf-8")
    return src_path, out_path


def _manifest_item(src_path: Path, out_path: Path, **overrides: Any) -> Dict[str, object]:
    item: Dict[str, object] = {
        "source_url": SOURCE_URL,
        "source_path": str(src_path),
        "final_path": str(out_path),
        "status": CRAWL_STATUS_FETCHED,
        "title": "Runner Test",
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


def _long_zh_body() -> str:
    return "中文正文内容足够长。" * 15


class TestRunQa:
    def test_pass_case(self, tmp_path: Path) -> None:
        body = _long_zh_body()
        src_path, out_path = _write_item_files(
            tmp_path,
            "001-pass",
            source=f"# Runner Test\n\n{body}",
            final=f"# Runner Test\n\n{body}",
        )
        manifest = {
            "batch_id": "batch-001",
            "config": {"skip_qa": False},
            "items": [_manifest_item(src_path, out_path)],
        }
        result = run_qa(manifest, batch_dir=tmp_path / "batch-001")
        assert result["qa_status"] == QA_STATUS_PASS
        assert result["technical_status"] == QA_STATUS_PASS
        assert result["content_status"] == QA_STATUS_PASS
        assert result["errors"] == []
        assert result["missing_files"] == []
        assert result["checked_items"] == 1
        assert "checked_at_utc" in result

    def test_skip_qa_in_manifest_config(self, tmp_path: Path) -> None:
        manifest = {
            "batch_id": "batch-001",
            "config": {"skip_qa": True},
            "items": [{"source_url": SOURCE_URL}],
        }
        result = run_qa(manifest)
        assert result["qa_status"] == QA_STATUS_SKIPPED
        assert result["technical_status"] == QA_STATUS_SKIPPED
        assert result["content_status"] == QA_STATUS_SKIPPED
        assert result["checked_items"] == 1
        assert result["errors"] == []

    def test_missing_files(self, tmp_path: Path) -> None:
        src_path, out_path = _write_item_files(
            tmp_path,
            "001-missing",
            source=f"# Runner Test\n\n{_long_zh_body()}",
            final=f"# Runner Test\n\n{_long_zh_body()}",
        )
        out_path.unlink()
        manifest = {
            "batch_id": "batch-001",
            "config": {},
            "items": [_manifest_item(src_path, out_path)],
        }
        result = run_qa(manifest, batch_dir=tmp_path / "batch-001")
        assert result["qa_status"] == QA_STATUS_FAIL
        assert result["technical_status"] == QA_STATUS_FAIL
        assert SOURCE_URL in result["missing_files"]
        assert any("missing_files:" in e for e in result["technical_errors"])

    def test_technical_and_content_failures_combined(self, tmp_path: Path) -> None:
        src_path, out_path = _write_item_files(
            tmp_path,
            "001-fail",
            source="# Runner Test\n\nEnglish only.",
            final="# Runner Test\n\nEnglish only.",
        )
        manifest = {
            "batch_id": "batch-001",
            "config": {},
            "items": [
                _manifest_item(
                    src_path,
                    out_path,
                    status=CRAWL_STATUS_FAILED_FETCH,
                    final_language="zh",
                )
            ],
        }
        result = run_qa(manifest, batch_dir=tmp_path / "batch-001")
        assert result["qa_status"] == QA_STATUS_FAIL
        assert result["technical_status"] == QA_STATUS_FAIL
        assert result["content_status"] == QA_STATUS_FAIL
        assert len(result["technical_errors"]) >= 1
        assert len(result["content_errors"]) >= 1

    def test_logs_on_failure(self, tmp_path: Path) -> None:
        src_path, out_path = _write_item_files(
            tmp_path,
            "001-log",
            source="# Runner Test\n\nshort",
            final="# Runner Test\n\nshort",
        )
        batch_dir = tmp_path / "batch-001"
        logger = PipelineLogger(tmp_path)
        manifest = {
            "batch_id": "batch-001",
            "config": {},
            "items": [_manifest_item(src_path, out_path)],
        }
        result = run_qa(manifest, logger=logger, batch_dir=batch_dir)
        assert result["qa_status"] == QA_STATUS_FAIL
        log_lines: List[str] = logger.log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(log_lines) == 1
        assert "qa_failed" in log_lines[0]
