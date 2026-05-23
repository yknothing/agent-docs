"""Batch QA runner combining technical and content gates."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from agent_docs.core.config import (
    DEFAULT_CHARSET,
    QA_LOG_MAX_ERRORS,
    QA_STATUS_FAIL,
    QA_STATUS_PASS,
    QA_STATUS_SKIPPED,
)
from agent_docs.core.logging import PipelineLogger
from agent_docs.qa.gates import run_content_qa_item, run_technical_qa_item


def run_qa(
    manifest: Dict[str, object],
    *,
    logger: Optional[PipelineLogger] = None,
    batch_dir: Optional[Path] = None,
) -> Dict[str, object]:
    cfg = manifest.get("config", {})
    batch_id = str(manifest.get("batch_id", ""))
    if isinstance(cfg, dict) and cfg.get("skip_qa"):
        item_count = len(manifest.get("items", []))
        return {
            "qa_status": QA_STATUS_SKIPPED,
            "technical_status": QA_STATUS_SKIPPED,
            "content_status": QA_STATUS_SKIPPED,
            "checked_items": item_count,
            "errors": [],
        }

    items = manifest.get("items", [])
    technical_errors: List[str] = []
    content_errors: List[str] = []
    missing: List[str] = []
    image_delta = 0
    table_delta = 0
    heading_delta = 0
    link_delta = 0

    for it in items:
        if not isinstance(it, dict):
            continue
        source_url = str(it.get("source_url"))
        src_path = Path(str(it.get("source_path", "")))
        out_path = Path(str(it.get("final_path", "")))
        if not src_path.exists() or not out_path.exists():
            missing.append(source_url)
            technical_errors.append(f"missing_files: {source_url}")
            continue

        out_text = out_path.read_text(encoding=DEFAULT_CHARSET, errors="replace")
        tech_errs, deltas = run_technical_qa_item(it, out_text)
        technical_errors.extend(tech_errs)
        image_delta += deltas["image_count_delta"]
        table_delta += deltas["table_count_delta"]
        heading_delta += deltas["heading_count_delta"]
        link_delta += deltas["link_count_delta"]
        content_errors.extend(run_content_qa_item(it, out_text))

    technical_status = QA_STATUS_PASS if not technical_errors else QA_STATUS_FAIL
    content_status = QA_STATUS_PASS if not content_errors else QA_STATUS_FAIL
    errors = technical_errors + content_errors
    qa_status = QA_STATUS_PASS if technical_status == QA_STATUS_PASS and content_status == QA_STATUS_PASS else QA_STATUS_FAIL

    if logger and qa_status == QA_STATUS_FAIL:
        error_counts: Dict[str, int] = {}
        for err in errors:
            code = err.split(":", 1)[0].strip()
            error_counts[code] = error_counts.get(code, 0) + 1
        artifact = str(batch_dir / "batch_qa_report.json") if batch_dir else ""
        logger.log(
            "ERROR",
            "qa",
            batch_id=batch_id,
            error_code="qa_failed",
            message=f"{len(errors)} QA error(s)",
            error_counts=error_counts,
            errors=errors[:QA_LOG_MAX_ERRORS],
            artifact_path=artifact,
        )

    return {
        "qa_status": qa_status,
        "technical_status": technical_status,
        "content_status": content_status,
        "checked_items": len(items),
        "image_count_delta": image_delta,
        "table_count_delta": table_delta,
        "heading_count_delta": heading_delta,
        "link_count_delta": link_delta,
        "missing_files": missing,
        "errors": errors,
        "technical_errors": technical_errors,
        "content_errors": content_errors,
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
