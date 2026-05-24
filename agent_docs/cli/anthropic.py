"""Anthropic Stage 1 pipeline orchestration: discover, crawl, QA, optional sync."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from agent_docs.core.config import (
    ALLOWED_SITEMAP_PREFIXES,
    CRAWL_STATUS_FETCHED,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHARSET,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SYNC_TIMEOUT,
    DEFAULT_TRANSLATE_TIMEOUT,
    FEISHU_DOC_ROOT_MODE_DEFAULT,
    FEISHU_DOC_ROOT_MODE_PARENT,
    FEISHU_SYNC_FAIL_STATUSES,
    PIPELINE_OVERALL_STATUS_FAIL,
    PIPELINE_OVERALL_STATUS_PASS,
    QA_STATUS_PASS,
    QA_STATUS_SKIPPED,
)
from agent_docs.core.logging import PipelineLogger
from agent_docs.ingest import build_targets, process_target
from agent_docs.qa import run_qa
from agent_docs.sinks import sync_to_feishu


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding=DEFAULT_CHARSET)


def write_batch(
    batch_items: List[Dict[str, object]],
    batch_dir: Path,
    cfg: argparse.Namespace,
    *,
    logger: Optional[PipelineLogger] = None,
) -> Dict[str, object]:
    batch_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "batch_id": batch_dir.name,
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "items": batch_items,
        "config": {
            "batch_size": cfg.batch_size,
            "translate": cfg.translate,
            "translate_mode": cfg.translate_mode,
            "include_platform_docs": cfg.include_platform_docs,
            "include_code_docs": cfg.include_code_docs,
            "include_news": cfg.include_news,
            "allowed_news_prefixes": list(cfg.allowed_news_prefixes),
            "skip_qa": cfg.no_qa,
        },
    }
    if not cfg.no_qa:
        manifest["qa"] = run_qa(manifest, logger=logger, batch_dir=batch_dir)
    else:
        manifest["qa"] = {
            "qa_status": QA_STATUS_SKIPPED,
            "technical_status": QA_STATUS_SKIPPED,
            "content_status": QA_STATUS_SKIPPED,
            "checked_items": len(batch_items),
            "errors": [],
        }
    _write_json(batch_dir / "batch_qa_report.json", manifest["qa"])
    _write_json(batch_dir / "batch_manifest.json", manifest)
    return manifest


def commit_batch(batch_dir: Path) -> bool:
    try:
        subprocess.run(["git", "add", str(batch_dir)], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: add anthropic content batch {batch_dir.name}"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anthropic docs/news pipeline")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-items", type=int, default=0, help="Limit for smoke-run/validation")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--resume-output",
        action="store_true",
        help="Allow writing into an output root that already has batch directories",
    )
    parser.add_argument("--allowed-news-prefixes", nargs="+", default=sorted(ALLOWED_SITEMAP_PREFIXES))

    parser.add_argument("--translate", dest="translate", action="store_true")
    parser.add_argument("--no-translate", dest="translate", action="store_false")
    parser.set_defaults(translate=True)
    parser.add_argument("--translate-mode", choices=["auto", "command", "openai", "off"], default="auto")
    parser.add_argument("--translate-timeout", type=int, default=DEFAULT_TRANSLATE_TIMEOUT)

    parser.add_argument("--execute-feishu", action="store_true", help="Actually run lark-cli commands")
    parser.add_argument("--sync-feishu", action="store_true")
    parser.add_argument("--force-sync", action="store_true", help="Allow Feishu sync even when QA did not pass")
    parser.add_argument("--sync-timeout", type=int, default=DEFAULT_SYNC_TIMEOUT)
    parser.add_argument("--feishu-folder-token", default="")
    parser.add_argument(
        "--feishu-doc-root-mode",
        choices=[FEISHU_DOC_ROOT_MODE_DEFAULT, FEISHU_DOC_ROOT_MODE_PARENT],
        default=os.environ.get("FEISHU_DOC_ROOT_MODE", FEISHU_DOC_ROOT_MODE_DEFAULT),
        help="agent-docs-folder: FEISHU_DOC_FOLDER_TOKEN points to agent-docs/; parent: token is parent, pipeline creates agent-docs/",
    )

    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--force-commit", action="store_true")
    parser.add_argument("--allow-failures", action="store_true", help="Exit 0 even when fetch/QA/sync failed")
    parser.add_argument("--no-qa", action="store_true")
    parser.add_argument("--qa", dest="qa", action="store_true", help="(kept for compatibility)")
    parser.set_defaults(qa=True)

    source = parser.add_argument_group("source")
    source.add_argument("--include-platform-docs", dest="include_platform_docs", action="store_true", default=True)
    source.add_argument("--no-include-platform-docs", dest="include_platform_docs", action="store_false")
    source.add_argument("--include-code-docs", dest="include_code_docs", action="store_true", default=True)
    source.add_argument("--no-include-code-docs", dest="include_code_docs", action="store_false")
    source.add_argument("--include-news", dest="include_news", action="store_true", default=True)
    source.add_argument("--no-include-news", dest="include_news", action="store_false")
    source.add_argument(
        "--target-url",
        dest="target_urls",
        action="append",
        default=None,
        help="Limit crawl targets to exact source URLs (repeatable).",
    )

    parser.add_argument("--discover-only", action="store_true")

    args = parser.parse_args(argv)
    args.no_qa = args.no_qa or (not args.qa)
    return args


def discover_only(cfg: argparse.Namespace) -> Dict[str, object]:
    targets = build_targets(cfg)
    if cfg.max_items > 0:
        targets = targets[: cfg.max_items]
    out = Path(cfg.output_root) / "discover.json"
    Path(cfg.output_root).mkdir(parents=True, exist_ok=True)
    payload = {"count": len(targets), "items": targets}
    _write_json(out, payload)
    return payload


def run_pipeline(cfg: argparse.Namespace) -> Dict[str, object]:
    targets = build_targets(cfg)
    if cfg.max_items > 0:
        targets = targets[: cfg.max_items]

    out_root = Path(cfg.output_root).resolve()
    if out_root.exists() and not cfg.resume_output and any(out_root.glob("batch-*")):
        return {
            "output_root": str(out_root),
            "target_count": len(targets),
            "batch_count": 0,
            "overall_status": PIPELINE_OVERALL_STATUS_FAIL,
            "failed_batches": [],
            "errors": ["output_root already contains batch directories; pass --resume-output to append/reuse"],
            "items": [],
        }
    out_root.mkdir(parents=True, exist_ok=True)
    logger = PipelineLogger(out_root)
    logger.log(
        "INFO",
        "discover",
        message="pipeline_start",
        target_count=len(targets),
        batch_size=cfg.batch_size,
        output_root=str(out_root),
    )
    batches: List[Dict[str, object]] = []
    all_items: List[Dict[str, object]] = []

    for batch_index in range(0, len(targets), cfg.batch_size):
        this_batch = targets[batch_index : batch_index + cfg.batch_size]
        batch_name = f"batch-{batch_index // cfg.batch_size + 1:03d}"
        batch_dir = out_root / batch_name
        batch_items: List[Dict[str, object]] = []
        item_total = len(this_batch)
        logger.log(
            "INFO",
            "crawl",
            batch_id=batch_name,
            message="batch_start",
            item_index=1,
            item_total=item_total,
        )
        for i, t in enumerate(this_batch):
            item = process_target(
                t,
                cfg,
                batch_dir,
                batch_index + i + 1,
                logger=logger,
                batch_id=batch_name,
                item_index=i + 1,
                item_total=item_total,
            )
            batch_items.append(item)
            all_items.append(item)
        fetched = sum(
            1 for it in batch_items if isinstance(it, dict) and it.get("status") == CRAWL_STATUS_FETCHED
        )
        logger.log(
            "INFO",
            "crawl",
            batch_id=batch_name,
            message="batch_crawl_complete",
            items_fetched=fetched,
            items_total=item_total,
        )
        manifest = write_batch(batch_items, batch_dir, cfg, logger=logger)

        qa_ok = manifest.get("qa", {}).get("qa_status") == QA_STATUS_PASS
        if cfg.commit and (qa_ok or cfg.force_commit):
            committed = commit_batch(batch_dir)
            manifest["git_commit"] = committed
            _write_json(
                batch_dir / "batch_qa_report.json",
                {**manifest.get("qa", {}), "git_commit": committed},
            )
        elif cfg.commit and not qa_ok:
            manifest["git_commit"] = False
            _write_json(
                batch_dir / "batch_qa_report.json",
                {**manifest.get("qa", {}), "git_commit": False, "reason": "blocked_by_qa"},
            )

        if cfg.sync_feishu:
            sync_report = sync_to_feishu(manifest, cfg, batch_dir, out_root, logger=logger)
            manifest["feishu"] = sync_report
            if sync_report.get("status") in FEISHU_SYNC_FAIL_STATUSES:
                manifest.setdefault("qa", {}).setdefault("errors", []).append(
                    f"feishu_sync_{sync_report.get('status')}: {sync_report.get('reason', '')}"
                )
                _write_json(batch_dir / "batch_qa_report.json", manifest.get("qa", {}))
        manifest["batch_dir"] = str(batch_dir)
        _write_json(batch_dir / "batch_manifest.json", manifest)
        batches.append(manifest)

    failed_batches = []
    for batch in batches:
        qa_status = batch.get("qa", {}).get("qa_status")
        feishu_status = batch.get("feishu", {}).get("status")
        if qa_status not in {QA_STATUS_PASS, QA_STATUS_SKIPPED}:
            failed_batches.append(batch.get("batch_id"))
        if feishu_status in FEISHU_SYNC_FAIL_STATUSES:
            failed_batches.append(batch.get("batch_id"))

    summary = {
        "output_root": str(out_root),
        "target_count": len(targets),
        "batch_count": len(batches),
        "overall_status": PIPELINE_OVERALL_STATUS_FAIL if failed_batches else PIPELINE_OVERALL_STATUS_PASS,
        "failed_batches": sorted(set(str(x) for x in failed_batches if x)),
        "items": all_items,
    }
    summary_path = out_root / "pipeline_summary.json"
    _write_json(summary_path, summary)
    logger.log(
        "INFO" if summary["overall_status"] == PIPELINE_OVERALL_STATUS_PASS else "ERROR",
        "discover",
        message="pipeline_complete",
        overall_status=summary["overall_status"],
        batch_count=summary["batch_count"],
        failed_batches=summary["failed_batches"],
        artifact_path=str(summary_path),
    )
    return summary


def main(argv: Optional[List[str]] = None) -> None:
    cfg = parse_args(argv)
    if cfg.discover_only or os.environ.get("ANTHROPIC_PIPELINE_DISCOVER_ONLY"):
        print(json.dumps(discover_only(cfg), ensure_ascii=False, indent=2))
        return
    report = run_pipeline(cfg)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("overall_status") != PIPELINE_OVERALL_STATUS_PASS and not cfg.allow_failures:
        sys.exit(1)
