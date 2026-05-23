#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_docs.core.config import (  # noqa: E402
    AGENT_DOCS_ROOT,
    ALLOWED_DOC_HOSTS,
    ALLOWED_SITEMAP_PREFIXES,
    CODE_DOCS_URL,
    DEFAULT_BATCH_SIZE,
    DEFAULT_IMAGE_FETCH_TIMEOUT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_TRANSLATE_TIMEOUT,
    DEFAULT_VENDOR,
    FEISHU_DOC_LOCALE_PREFIXES,
    FEISHU_EXCLUDED_URL_PATHS,
    FEISHU_FOLDER_CACHE_NAME,
    FEISHU_FOLDER_INDEX_NAME,
    FEISHU_INDEX_CACHE_NAME,
    FEISHU_INDEX_DOC_TITLE,
    FEISHU_VERIFY_MIN_CONTENT_LEN,
    IMAGE_EXTS,
    NEWS_HOSTS,
    PLATFORM_DOCS_URL,
    SITEMAP_URL,
    UA,
    DEFAULT_CHARSET,
    DEFAULT_SYNC_TIMEOUT,
    FEISHU_ALT_TEXT_MIN_LEN,
    FEISHU_ALT_TEXT_HINT_MAX_LEN,
    FEISHU_ERROR_SNIPPET_MAX_LEN,
    FEISHU_FOLDER_TOKEN_HASH_LEN,
    FEISHU_MEDIA_CAPTION_MAX_LEN,
    QA_STATUS_SKIPPED,
)
from agent_docs.core.logging import PipelineLogger  # noqa: E402
from agent_docs.vendors.registry import (  # noqa: E402
    VENDOR_LIBRARIES,
    feishu_brand_root,
    feishu_library_root,
)
from agent_docs.ingest import (
    build_targets,
    parse_frontmatter,
    process_target,
    safe_slug,
)
from agent_docs.qa import run_qa

import argparse
import datetime
import hashlib
import json
import os
import http.client
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import html as html_lib


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
    (batch_dir / "batch_qa_report.json").write_text(
        json.dumps(manifest["qa"], ensure_ascii=False, indent=2),
        encoding=DEFAULT_CHARSET,
    )
    manifest_path = batch_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding=DEFAULT_CHARSET)
    return manifest


def commit_batch(batch_dir: Path) -> bool:
    try:
        subprocess.run(["git", "add", str(batch_dir)], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: add anthropic content batch {batch_dir.name}"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def parse_doc_id_from_output(text: str) -> Optional[str]:
    if not text:
        return None
    candidates = re.finditer(r"\{.*\}", text, flags=re.DOTALL)
    decoder = json.JSONDecoder()
    for m in candidates:
        chunk = m.group(0)
        try:
            obj = decoder.raw_decode(chunk)[0]
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        if isinstance(data, dict):
            if isinstance(data.get("token"), str):
                return data["token"]
            if isinstance(data.get("document_id"), str):
                return data["document_id"]
            if isinstance(data.get("url"), str):
                return data["url"]
            doc = data.get("document")
            if isinstance(doc, dict) and isinstance(doc.get("document_id"), str):
                return doc["document_id"]
            if isinstance(doc, dict) and isinstance(doc.get("url"), str):
                return doc["url"]
        if isinstance(obj.get("data"), dict) and isinstance(obj.get("data", {}).get("data"), dict):
            nested = obj["data"]["data"]
            if isinstance(nested, dict):
                if isinstance(nested.get("token"), str):
                    return nested["token"]
                if isinstance(nested.get("document_id"), str):
                    return nested["document_id"]
                if isinstance(nested.get("url"), str):
                    return nested["url"]
                doc = nested.get("document")
                if isinstance(doc, dict) and isinstance(doc.get("document_id"), str):
                    return doc["document_id"]
                if isinstance(doc, dict) and isinstance(doc.get("url"), str):
                    return doc["url"]

    regex_candidates = re.findall(
        r"""(?:"document_id"\s*:\s*"([^"]+)"|\"document_id\"\s*:\s*'([^']+)'|"token"\s*:\s*"([^"]+)"|document_id[:=]\s*([A-Za-z0-9_-]+)|doc(?:ument)?_id[:=]\s*([A-Za-z0-9_-]+))""",
        text,
    )
    for groups in regex_candidates:
        for value in groups:
            if value:
                return value
    url_candidate = re.search(r"https://[A-Za-z0-9./?=&_%#:-]*docx[A-Za-z0-9./?=&_%#:-]*", text)
    if url_candidate:
        return url_candidate.group(0)
    return None


def parse_lark_cli_json(text: str) -> Optional[Dict[str, object]]:
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def feishu_doc_root_mode(cfg: argparse.Namespace) -> str:
    return str(
        getattr(
            cfg,
            "feishu_doc_root_mode",
            os.environ.get("FEISHU_DOC_ROOT_MODE", "agent-docs-folder"),
        )
    )


def feishu_folder_segment_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "untitled"


def feishu_should_skip_sync(source_url: str) -> bool:
    path = urllib.parse.urlparse(source_url).path.lower()
    return any(path.startswith(prefix) for prefix in FEISHU_EXCLUDED_URL_PATHS)


def feishu_strip_docs_path(path_segs: List[str]) -> List[str]:
    segs = list(path_segs)
    if segs and segs[0] == "docs":
        segs = segs[1:]
    if segs and segs[0].lower() in FEISHU_DOC_LOCALE_PREFIXES:
        segs = segs[1:]
    return segs


def feishu_path_base(cfg: argparse.Namespace, vendor: str = DEFAULT_VENDOR) -> List[str]:
    """Folder segments relative to FEISHU_DOC_FOLDER_TOKEN (used for lark-cli mkdir).

    ``agent-docs-folder`` (default): token points at existing ``agent-docs/`` folder;
    segments start at ``anthropic-docs/Anthropic/…``.

    ``parent``: token is parent of ``agent-docs``; segments include ``agent-docs/`` first.
    """
    lib_root = feishu_library_root(vendor)
    brand_root = feishu_brand_root(vendor)
    if feishu_doc_root_mode(cfg) == "parent":
        return [AGENT_DOCS_ROOT, lib_root, brand_root]
    return [lib_root, brand_root]


def feishu_full_folder_path(folder_segments: Sequence[str], cfg: Optional[argparse.Namespace] = None) -> str:
    """Full Feishu path from Drive root for reports and acceptance checks.

    In ``agent-docs-folder`` mode the token already sits inside ``agent-docs/``, but
    reports must still show ``agent-docs/anthropic-docs/…`` so humans and E2E
    checklists match the intended layout.
    """
    segs = list(folder_segments)
    if not segs:
        return ""
    if feishu_doc_root_mode(cfg) == "parent":
        return "/".join(segs)
    if segs[0] == AGENT_DOCS_ROOT:
        return "/".join(segs)
    return "/".join([AGENT_DOCS_ROOT, *segs])


def feishu_folder_segments(
    source_url: str,
    source_type: str = "",
    cfg: Optional[argparse.Namespace] = None,
    vendor: str = DEFAULT_VENDOR,
) -> List[str]:
    """Map source URL to folder segments under FEISHU_DOC_FOLDER_TOKEN."""
    parsed = urllib.parse.urlparse(source_url)
    host = parsed.netloc.lower()
    path_segs = [s for s in parsed.path.strip("/").split("/") if s]
    ns = cfg or argparse.Namespace()
    base = feishu_path_base(ns, vendor=vendor)

    if host == "platform.claude.com":
        doc_path = feishu_strip_docs_path(path_segs)
        parent = doc_path[:-1] if len(doc_path) > 1 else []
        return base + ["Developer-docs", *[feishu_folder_segment_name(s) for s in parent]]

    if host == "code.claude.com":
        doc_path = feishu_strip_docs_path(path_segs)
        parent = doc_path[:-1] if len(doc_path) > 1 else []
        return base + ["Developer-docs", "Claude Code", *[feishu_folder_segment_name(s) for s in parent]]

    if host in {"www.anthropic.com", "anthropic.com"}:
        if not path_segs:
            return base + ["Other"]
        first = path_segs[0].lower()
        category_map = {
            "learn": "Anthropic Academy",
            "engineering": "Engineering",
            "news": "News",
            "research": "Research",
            "economic-futures": "Economic Futures",
            "system-cards": "System Cards",
        }
        category = category_map.get(first, feishu_folder_segment_name(path_segs[0]))
        rest = path_segs[1:-1] if len(path_segs) > 1 else []
        return base + [category, *[feishu_folder_segment_name(s) for s in rest]]

    if host in {"claude.com", "www.claude.com"}:
        lower_path = parsed.path.lower()
        if lower_path.startswith("/resources/courses"):
            return []
        if path_segs and path_segs[0].lower() == "blog":
            rest = path_segs[1:-1] if len(path_segs) > 2 else []
            return base + ["Claude", "Blog", *[feishu_folder_segment_name(s) for s in rest]]
        if len(path_segs) >= 2 and path_segs[0].lower() == "resources":
            resource_map = {
                "tutorials": "Tutorials",
                "use-cases": "User Cases",
            }
            category = resource_map.get(path_segs[1].lower())
            if category:
                rest = path_segs[2:-1] if len(path_segs) > 3 else []
                return base + [category, *[feishu_folder_segment_name(s) for s in rest]]
        return base + ["Claude", "Other"]

    # Legacy source_type fallback when URL host is unexpected.
    legacy_map = {
        "platform_docs": ["Developer-docs"],
        "claude_code_docs": ["Developer-docs", "Claude Code"],
        "anthropic_news": ["News"],
    }
    if source_type in legacy_map:
        return base + legacy_map[source_type]
    return base + ["Other"]


def feishu_safe_name(title: str, max_len: int = 80) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", title.strip())
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"-import$", "", name, flags=re.IGNORECASE)
    if not name:
        name = "untitled"
    return name[:max_len]


def build_feishu_source_attribution_block(meta: Dict[str, object]) -> str:
    """Visible source attribution for Feishu import (frontmatter is stripped on import)."""
    source_url = str(meta.get("source_url") or "").strip()
    if not source_url:
        return ""
    published_at = str(meta.get("published_at") or "—").strip()
    lines = [
        "> **资料来源**",
        f"> - 原文链接：[{source_url}]({source_url})",
        f"> - 发布时间：{published_at}",
    ]
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def sanitize_feishu_import_markdown(body: str) -> Tuple[str, List[str]]:
    """Prepare markdown for drive +import: remove broken local media refs, keep alt text."""
    image_alts: List[str] = []

    def replace_md_image(match: re.Match[str]) -> str:
        alt = match.group(1).strip() or "image"
        image_alts.append(alt)
        return f"\n\n**[图] {alt}**\n\n"

    cleaned = body
    cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", replace_md_image, cleaned)
    cleaned = re.sub(r"<img[^>]+>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\uFFFD", "", cleaned)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n", image_alts


def prepare_feishu_import_markdown(final_path: Path, payload_file: Path) -> Tuple[Path, List[str]]:
    raw = final_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    attribution = build_feishu_source_attribution_block(meta)
    body, image_alts = sanitize_feishu_import_markdown(body)
    if attribution:
        body = attribution + body
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(body, encoding="utf-8")
    return payload_file, image_alts


def load_feishu_folder_cache(cache_path: Path) -> Dict[str, str]:
    if not cache_path.exists():
        return {}
    try:
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): str(v) for k, v in loaded.items()}


def save_feishu_folder_cache(cache_path: Path, cache: Dict[str, str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def load_feishu_index_cache(cache_path: Path) -> Dict[str, str]:
    if not cache_path.exists():
        return {}
    try:
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): str(v) for k, v in loaded.items()}


def save_feishu_index_cache(cache_path: Path, cache: Dict[str, str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _md_table_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _md_table_link(url: str, label: Optional[str] = None) -> str:
    if not url:
        return "—"
    return f"[{_md_table_cell(label or url)}]({url})"


def build_folder_index_markdown(folder_path: str, items: List[Dict]) -> str:
    lines = [
        f"# {FEISHU_INDEX_DOC_TITLE}",
        "",
        f"**目录路径**：`{folder_path}`",
        "",
        "| 标题 | 原文链接 | 发布时间 | 飞书文档 | 状态 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        title = _md_table_cell(str(item.get("title") or "Untitled"))
        source_url = str(item.get("source_url") or "")
        doc_url = str(item.get("doc_url") or "")
        published_at = _md_table_cell(str(item.get("published_at") or "—"))
        status = _md_table_cell(str(item.get("status") or ""))
        source_cell = _md_table_link(source_url)
        doc_cell = _md_table_link(doc_url, "打开") if doc_url else "—"
        lines.append(
            f"| {title} | {source_cell} | {published_at} | {doc_cell} | {status} |"
        )
    return "\n".join(lines) + "\n"


def feishu_index_file_suffix(folder_token: str) -> str:
    if folder_token.startswith("${"):
        return hashlib.md5(folder_token.encode(DEFAULT_CHARSET)).hexdigest()[:FEISHU_FOLDER_TOKEN_HASH_LEN]
    token = folder_token.strip()
    return token[-FEISHU_FOLDER_TOKEN_HASH_LEN:] if len(token) >= FEISHU_FOLDER_TOKEN_HASH_LEN else token or "unknown"


def merge_folder_index_items(existing: List[Dict], new_items: List[Dict]) -> List[Dict]:
    by_url: Dict[str, Dict] = {}
    for item in existing:
        if isinstance(item, dict):
            by_url[str(item.get("source_url", ""))] = item
    for item in new_items:
        if isinstance(item, dict):
            by_url[str(item.get("source_url", ""))] = item
    return sorted(by_url.values(), key=lambda x: str(x.get("title", "")))


def load_feishu_folder_index(index_path: Path) -> Dict[str, object]:
    if not index_path.exists():
        return {"folders": {}}
    try:
        loaded = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {"folders": {}}
    if not isinstance(loaded, dict):
        return {"folders": {}}
    folders = loaded.get("folders")
    if not isinstance(folders, dict):
        folders = {}
    return {"folders": folders, **{k: v for k, v in loaded.items() if k != "folders"}}


def save_feishu_folder_index(index_path: Path, payload: Dict[str, object]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_feishu_folder_indexes(
    sync_items: List[Dict[str, object]],
    manifest_items: List[object],
    cfg: argparse.Namespace,
    batch_dir: Path,
    out_root: Path,
    script_path: Path,
    sync_dir: Path,
    *,
    logger: Optional[PipelineLogger] = None,
    batch_id: str = "",
    sync_stage: str = "sync_dryrun",
) -> List[Dict[str, object]]:
    manifest_by_url: Dict[str, Dict] = {}
    for it in manifest_items:
        if isinstance(it, dict) and it.get("source_url"):
            manifest_by_url[str(it["source_url"])] = it

    groups: Dict[str, Dict[str, object]] = {}
    for sync_item in sync_items:
        if not isinstance(sync_item, dict):
            continue
        folder_token = sync_item.get("folder_token")
        if not folder_token:
            continue
        folder_path = str(sync_item.get("folder_path") or "")
        source_url = str(sync_item.get("source_url") or "")
        manifest_item = manifest_by_url.get(source_url, {})
        index_item = {
            "title": sync_item.get("title") or manifest_item.get("title") or source_url,
            "source_url": source_url,
            "selected_url": manifest_item.get("selected_url") or source_url,
            "published_at": manifest_item.get("published_at"),
            "doc_url": sync_item.get("doc_url"),
            "captured_at_utc": manifest_item.get("captured_at_utc"),
            "status": sync_item.get("status"),
        }
        token_key = str(folder_token)
        if token_key not in groups:
            groups[token_key] = {"folder_path": folder_path, "items": []}
        group_items = groups[token_key].get("items")
        if isinstance(group_items, list):
            group_items.append(index_item)

    if not groups:
        return []

    index_cache_path = out_root / FEISHU_INDEX_CACHE_NAME
    index_cache = load_feishu_index_cache(index_cache_path)
    folder_index_path = out_root / FEISHU_FOLDER_INDEX_NAME
    folder_index_payload = load_feishu_folder_index(folder_index_path)
    folders_map = folder_index_payload.setdefault("folders", {})
    if not isinstance(folders_map, dict):
        folders_map = {}
        folder_index_payload["folders"] = folders_map

    index_reports: List[Dict[str, object]] = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for folder_token, group in groups.items():
        folder_path = str(group.get("folder_path") or "")
        raw_items = group.get("items")
        index_items = [x for x in raw_items if isinstance(x, dict)] if isinstance(raw_items, list) else []
        index_items.sort(key=lambda x: str(x.get("title", "")))
        index_md = build_folder_index_markdown(folder_path, index_items)
        token_suffix = feishu_index_file_suffix(folder_token)
        index_file = sync_dir / f"index_{token_suffix}.md"
        index_file.write_text(index_md, encoding="utf-8")
        index_rel = index_file.relative_to(out_root)
        cached_doc_id = index_cache.get(folder_token)

        if isinstance(folders_map, dict):
            existing = folders_map.get(folder_path, [])
            merged = merge_folder_index_items(existing if isinstance(existing, list) else [], index_items)
            folders_map[folder_path] = merged

        report: Dict[str, object] = {
            "folder_token": folder_token,
            "folder_path": folder_path,
            "index_file": str(index_file),
            "item_count": len(index_items),
            "doc_id": cached_doc_id,
            "action": "pending",
        }

        if cached_doc_id:
            update_cmd = [
                "lark-cli",
                "docs",
                "+update",
                "--api-version",
                "v2",
                "--doc",
                cached_doc_id,
                "--markdown",
                str(index_rel),
                "--mode",
                "overwrite",
            ]
            update_cmd_str = " ".join(shlex.quote(x) for x in update_cmd)
            if not cfg.execute_feishu:
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{update_cmd_str}\n")
                report["action"] = "dry-run-update"
                report["command"] = update_cmd_str
                if logger:
                    logger.log(
                        "INFO",
                        sync_stage,
                        batch_id=batch_id,
                        message="folder_index_dryrun_update",
                        folder_path=folder_path,
                        folder_token=folder_token,
                        doc_id=cached_doc_id,
                        artifact_path=str(index_file),
                    )
            else:
                rc, out, _ = run_lark_cli(update_cmd, out_root, cfg.sync_timeout)
                if rc == 0:
                    report["action"] = "updated"
                    report["command"] = update_cmd_str
                    if logger:
                        logger.log(
                            "INFO",
                            sync_stage,
                            batch_id=batch_id,
                            message="folder_index_updated",
                            folder_path=folder_path,
                            folder_token=folder_token,
                            doc_id=cached_doc_id,
                            artifact_path=str(index_file),
                        )
                else:
                    if logger:
                        logger.log(
                            "WARN",
                            sync_stage,
                            batch_id=batch_id,
                            error_code="folder_index_update_failed",
                            message=f"docs +update rc={rc}; fallback to re-import",
                            folder_path=folder_path,
                            folder_token=folder_token,
                            doc_id=cached_doc_id,
                            artifact_path=str(index_file),
                        )
                    cached_doc_id = None

        if not cached_doc_id:
            import_cmd = [
                "lark-cli",
                "drive",
                "+import",
                "--file",
                str(index_rel),
                "--folder-token",
                folder_token,
                "--type",
                "docx",
                "--name",
                FEISHU_INDEX_DOC_TITLE,
            ]
            import_cmd_str = " ".join(shlex.quote(x) for x in import_cmd)
            if not cfg.execute_feishu:
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{import_cmd_str}\n")
                report["action"] = "dry-run-import"
                report["command"] = import_cmd_str
                if logger:
                    logger.log(
                        "INFO",
                        sync_stage,
                        batch_id=batch_id,
                        message="folder_index_dryrun_import",
                        folder_path=folder_path,
                        folder_token=folder_token,
                        artifact_path=str(index_file),
                    )
            else:
                rc, out, _ = run_lark_cli(import_cmd, out_root, cfg.sync_timeout)
                if rc != 0:
                    report["action"] = f"import_failed({rc})"
                    if logger:
                        logger.log(
                            "ERROR",
                            sync_stage,
                            batch_id=batch_id,
                            error_code="folder_index_import_failed",
                            message=f"drive +import rc={rc}",
                            folder_path=folder_path,
                            folder_token=folder_token,
                            artifact_path=str(index_file),
                        )
                else:
                    doc_id = parse_doc_id_from_output(out)
                    if doc_id:
                        index_cache[folder_token] = doc_id
                        report["doc_id"] = doc_id
                        report["doc_url"] = f"https://my.feishu.cn/docx/{doc_id}"
                        report["action"] = "imported"
                        if logger:
                            logger.log(
                                "INFO",
                                sync_stage,
                                batch_id=batch_id,
                                message="folder_index_imported",
                                folder_path=folder_path,
                                folder_token=folder_token,
                                doc_id=doc_id,
                                artifact_path=str(index_file),
                            )
                    else:
                        report["action"] = "import_no_doc_id"
                        if logger:
                            logger.log(
                                "ERROR",
                                sync_stage,
                                batch_id=batch_id,
                                error_code="folder_index_no_doc_id",
                                message="import succeeded but doc_id missing",
                                folder_path=folder_path,
                                folder_token=folder_token,
                                artifact_path=str(index_file),
                            )

        index_reports.append(report)

    folder_index_payload["updated_at_utc"] = now
    save_feishu_folder_index(folder_index_path, folder_index_payload)
    save_feishu_index_cache(index_cache_path, index_cache)
    return index_reports


def feishu_folder_cache_key(parent_token: str, name: str) -> str:
    return f"{parent_token}::{name}"


def image_selection_hint(marker: str) -> Optional[str]:
    if not marker:
        return None
    alt_match = re.search(r"!\[([^\]]*)\]", marker)
    if alt_match:
        alt = alt_match.group(1).strip()
        if len(alt) >= FEISHU_ALT_TEXT_MIN_LEN:
            return alt[: min(FEISHU_ALT_TEXT_HINT_MAX_LEN, len(alt))]
        if alt:
            return alt
    return None


def run_lark_cli(args: Sequence[str], cwd: Path, timeout: int) -> Tuple[int, str, str]:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out, proc.stderr or ""


def ensure_feishu_folder(
    name: str,
    parent_token: str,
    cache: Dict[str, str],
    cache_key: str,
    cfg: argparse.Namespace,
    cwd: Path,
) -> str:
    stable_key = feishu_folder_cache_key(parent_token, name)
    if stable_key in cache:
        return cache[stable_key]
    if cache_key in cache:
        return cache[cache_key]
    if not cfg.execute_feishu:
        placeholder = f"${{FEISHU_FOLDER_{cache_key}}}"
        cache[stable_key] = placeholder
        cache[cache_key] = placeholder
        return placeholder
    rc, out, _ = run_lark_cli(
        ["lark-cli", "drive", "+create-folder", "--name", name, "--folder-token", parent_token],
        cwd,
        cfg.sync_timeout,
    )
    parsed = parse_lark_cli_json(out)
    token = None
    if parsed and parsed.get("ok") and isinstance(parsed.get("data"), dict):
        token = parsed["data"].get("folder_token")
    if not token:
        raise RuntimeError(f"create-folder failed for {name}: rc={rc} {out[:FEISHU_ERROR_SNIPPET_MAX_LEN]}")
    cache[stable_key] = str(token)
    cache[cache_key] = str(token)
    return str(token)


def verify_feishu_document(doc_id: str, cfg: argparse.Namespace, min_len: int = FEISHU_VERIFY_MIN_CONTENT_LEN) -> Dict[str, object]:
    if not cfg.execute_feishu:
        return {"verified": True, "reason": "dry-run"}
    rc, out, _ = run_lark_cli(
        ["lark-cli", "docs", "+fetch", "--api-version", "v2", "--doc", doc_id],
        Path.cwd(),
        cfg.sync_timeout,
    )
    parsed = parse_lark_cli_json(out)
    if rc != 0 or not parsed or not parsed.get("ok"):
        return {"verified": False, "reason": "fetch_failed", "raw": out[:500]}
    content = ""
    data = parsed.get("data")
    if isinstance(data, dict):
        doc = data.get("document")
        if isinstance(doc, dict) and isinstance(doc.get("content"), str):
            content = doc["content"]
    visible = re.sub(r"<[^>]+>", "", content)
    visible = re.sub(r"\s+", "", visible)
    image_count = len(re.findall(r"<img\b", content, flags=re.IGNORECASE))
    return {
        "verified": len(visible) >= min_len,
        "content_length": len(visible),
        "image_count": image_count,
        "min_required": min_len,
    }


def sync_to_feishu(
    manifest: Dict[str, object],
    cfg: argparse.Namespace,
    batch_dir: Path,
    out_root: Path,
    *,
    logger: Optional[PipelineLogger] = None,
) -> Dict[str, object]:
    if not cfg.sync_feishu:
        return {"status": "SKIPPED", "reason": "sync-feishu-disabled"}
    out_root = out_root.resolve()
    batch_dir = batch_dir.resolve()
    batch_id = str(manifest.get("batch_id", batch_dir.name))
    sync_stage = "sync_execute" if cfg.execute_feishu else "sync_dryrun"
    qa_status = manifest.get("qa", {}).get("qa_status")
    if qa_status != "PASS" and not cfg.force_sync:
        if logger:
            logger.log(
                "WARN",
                sync_stage,
                batch_id=batch_id,
                error_code="sync_blocked",
                message=f"QA status {qa_status}",
                artifact_path=str(batch_dir / "feishu_sync_report.json"),
            )
        return {"status": "BLOCKED", "reason": f"qa_status={qa_status}", "items": []}

    folder_token = cfg.feishu_folder_token or os.environ.get("FEISHU_DOC_FOLDER_TOKEN")
    if cfg.execute_feishu and not folder_token:
        if logger:
            logger.log(
                "ERROR",
                sync_stage,
                batch_id=batch_id,
                error_code="feishu_token_missing",
                message="FEISHU_DOC_FOLDER_TOKEN missing",
            )
        return {"status": "FAIL", "reason": "FEISHU_DOC_FOLDER_TOKEN missing"}
    if cfg.execute_feishu and not shutil.which("lark-cli"):
        if logger:
            logger.log(
                "ERROR",
                sync_stage,
                batch_id=batch_id,
                error_code="lark_cli_missing",
                message="lark-cli not installed",
            )
        return {"status": "FAIL", "reason": "lark-cli not installed"}

    root_token = folder_token or "${FEISHU_DOC_FOLDER_TOKEN}"
    folder_cache_path = out_root / FEISHU_FOLDER_CACHE_NAME
    folder_cache = load_feishu_folder_cache(folder_cache_path)
    if cfg.execute_feishu:
        placeholder_keys = [
            k
            for k, v in folder_cache.items()
            if isinstance(v, str) and v.startswith("${FEISHU_FOLDER_") and v.endswith("}")
        ]
        if placeholder_keys:
            for key in placeholder_keys:
                folder_cache.pop(key, None)
            if logger:
                logger.log(
                    "WARN",
                    sync_stage,
                    batch_id=batch_id,
                    error_code="feishu_folder_cache_placeholder_reset",
                    message="removed placeholder folder tokens before execute-sync; stale from dry-run",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                )

    items = manifest.get("items", [])
    total = len(items)
    fail: List[str] = []
    media_upload_count = 0
    item_success = 0
    sync_items: List[Dict[str, object]] = []
    script_path = batch_dir / "feishu_sync_commands.sh"
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"cd {shlex.quote(str(out_root))}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    sync_dir = batch_dir / "sync_payload"
    sync_dir.mkdir(parents=True, exist_ok=True)

    for item_index, it in enumerate(items, start=1):
        if not isinstance(it, dict):
            continue
        source_url = str(it.get("source_url"))
        log_ctx = {"batch_id": batch_id, "item_total": total, "item_index": item_index}
        title = str(it.get("title", source_url))
        final_path = Path(str(it.get("final_path", "")))
        source_type = str(it.get("source_type", ""))
        slug = str(it.get("slug", safe_slug(source_url)))
        media_items = it.get("images", [])
        if not final_path.exists():
            fail.append(f"{source_url}: final path missing")
            if logger:
                logger.log(
                    "ERROR",
                    sync_stage,
                    **log_ctx,
                    error_code="sync_item_missing_final",
                    message="final_path missing for sync",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                    source_url=source_url,
                )
            sync_items.append({"source_url": source_url, "status": "failed(final-path-missing)"})
            continue

        payload_file = sync_dir / f"{slug}.feishu.md"
        _, _image_alts = prepare_feishu_import_markdown(final_path, payload_file)
        payload_rel = payload_file.relative_to(out_root)
        import_name = feishu_safe_name(title)

        if feishu_should_skip_sync(source_url):
            if logger:
                logger.log(
                    "INFO",
                    sync_stage,
                    **log_ctx,
                    message="sync skipped by URL policy",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                    source_url=source_url,
                    reason="excluded-url",
                )
            sync_items.append(
                {
                    "source_url": source_url,
                    "status": "skipped(excluded-url)",
                    "reason": "courses/video-only path excluded in this phase",
                }
            )
            continue
        folder_segments = feishu_folder_segments(source_url, source_type, cfg)
        if not folder_segments:
            if logger:
                logger.log(
                    "WARN",
                    sync_stage,
                    **log_ctx,
                    error_code="sync_no_folder_segments",
                    message="folder mapping returned empty",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                    source_url=source_url,
                )
            sync_items.append({"source_url": source_url, "status": "skipped(no-folder-path)"})
            continue

        try:
            target_folder = root_token
            for idx, segment in enumerate(folder_segments):
                cache_key = "/".join(folder_segments[: idx + 1])
                target_folder = ensure_feishu_folder(segment, target_folder, folder_cache, cache_key, cfg, out_root)
        except Exception as e:
            fail.append(f"{source_url}: folder setup failed({type(e).__name__})")
            if logger:
                logger.log(
                    "ERROR",
                    sync_stage,
                    **log_ctx,
                    error_code="feishu_folder_setup_failed",
                    message=f"{type(e).__name__}: {e}",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                    source_url=source_url,
                    folder_segments=folder_segments,
                )
            sync_items.append({"source_url": source_url, "status": f"folder_failed({type(e).__name__})"})
            continue

        import_cmd = [
            "lark-cli",
            "drive",
            "+import",
            "--file",
            str(payload_rel),
            "--folder-token",
            target_folder,
            "--type",
            "docx",
            "--name",
            import_name,
        ]
        import_cmd_str = " ".join(shlex.quote(x) for x in import_cmd)
        with script_path.open("a", encoding="utf-8") as sf:
            sf.write(f"{import_cmd_str}\n")

        item_report: Dict[str, object] = {
            "source_url": source_url,
            "title": title,
            "folder_segments": folder_segments,
            "folder_path": feishu_full_folder_path(folder_segments, cfg),
            "folder_token": target_folder,
            "import_command": import_cmd_str,
            "status": "pending",
            "doc_id": None,
            "media_upload_count": 0,
            "media_uploads": [],
            "verification": None,
        }

        if not cfg.execute_feishu:
            planned_media = 0
            for image in media_items:
                if not isinstance(image, dict) or image.get("status") != "ok" or not image.get("file"):
                    continue
                image_path = Path(str(image["file"]))
                if not image_path.is_file():
                    continue
                media_upload_cmd = [
                    "lark-cli",
                    "docs",
                    "+media-insert",
                    "--doc",
                    "<DOC_ID_FROM_IMPORT>",
                    "--file",
                    f"{image_path.resolve().relative_to(out_root)}",
                    "--type",
                    "image",
                ]
                if isinstance(image.get("marker"), str):
                    alt_match = re.search(r"!\[([^\]]*)\]", str(image.get("marker")))
                    if alt_match and alt_match.group(1).strip():
                        media_upload_cmd.extend(["--caption", alt_match.group(1).strip()[:FEISHU_MEDIA_CAPTION_MAX_LEN]])
                media_cmd_str = " ".join(shlex.quote(x) for x in media_upload_cmd)
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{media_cmd_str}\n")
                item_report["media_uploads"].append(media_cmd_str)
                planned_media += 1
            item_report["media_upload_count"] = planned_media
            item_report["status"] = "ok-dry-run"
            sync_items.append(item_report)
            item_success += 1
            continue

        try:
            rc, out, _ = run_lark_cli(import_cmd, out_root, cfg.sync_timeout)
            if rc != 0:
                fail.append(f"{source_url}: import failed({rc})")
                if logger:
                    logger.log(
                        "ERROR",
                        sync_stage,
                        **log_ctx,
                        error_code="feishu_import_failed",
                        message=f"drive +import exited {rc}",
                        artifact_path=str(batch_dir / "feishu_sync_report.json"),
                        source_url=source_url,
                        import_command=import_cmd_str,
                    )
                item_report["status"] = f"import_failed({rc})"
                sync_items.append(item_report)
                continue
            doc_id = parse_doc_id_from_output(out)
            if not doc_id:
                fail.append(f"{source_url}: import succeeded but no doc_id")
                if logger:
                    logger.log(
                        "ERROR",
                        sync_stage,
                        **log_ctx,
                        error_code="feishu_import_no_doc_id",
                        message="import output missing doc_id",
                        artifact_path=str(batch_dir / "feishu_sync_report.json"),
                        source_url=source_url,
                        import_stdout=out[:400],
                    )
                item_report["status"] = "import_no_doc_id"
                sync_items.append(item_report)
                continue
            item_report["doc_id"] = doc_id
            item_report["doc_url"] = f"https://my.feishu.cn/docx/{doc_id}"

            expected_images = sum(
                1
                for image in media_items
                if isinstance(image, dict) and image.get("status") == "ok" and image.get("file")
            )
            item_report["expected_images"] = expected_images
            item_media_uploaded = 0
            media_failures: List[str] = []
            for image in media_items:
                if not isinstance(image, dict) or image.get("status") != "ok" or not image.get("file"):
                    continue
                image_path = Path(str(image["file"]))
                if not image_path.is_file():
                    continue
                media_upload_cmd = [
                    "lark-cli",
                    "docs",
                    "+media-insert",
                    "--doc",
                    doc_id,
                    "--file",
                    f"{image_path.resolve().relative_to(out_root)}",
                    "--type",
                    "image",
                ]
                if isinstance(image.get("marker"), str):
                    alt_match = re.search(r"!\[([^\]]*)\]", str(image.get("marker")))
                    if alt_match and alt_match.group(1).strip():
                        media_upload_cmd.extend(["--caption", alt_match.group(1).strip()[:FEISHU_MEDIA_CAPTION_MAX_LEN]])
                media_cmd_str = " ".join(shlex.quote(x) for x in media_upload_cmd)
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{media_cmd_str}\n")
                item_report["media_uploads"].append(media_cmd_str)
                media_rc, media_out, _ = run_lark_cli(media_upload_cmd, out_root, cfg.sync_timeout)
                if media_rc != 0:
                    media_failures.append(f"{image_path.name}({media_rc})")
                    if logger:
                        logger.log(
                            "WARN",
                            sync_stage,
                            **log_ctx,
                            error_code="feishu_media_upload_failed",
                            message=f"docs +media-insert failed for {image_path.name}: rc={media_rc}",
                            artifact_path=str(batch_dir / "feishu_sync_report.json"),
                            source_url=source_url,
                            doc_id=doc_id,
                        )
                    continue
                media_upload_count += 1
                item_media_uploaded += 1
            item_report["media_upload_count"] = item_media_uploaded
            item_report["media_failures"] = media_failures
            verification = verify_feishu_document(doc_id, cfg)
            item_report["verification"] = verification
            fetched_images = int(verification.get("image_count") or 0)
            if media_failures:
                item_report["status"] = "ok-content-media-partial"
                fail.extend(f"{source_url}: media-upload failed for {name}" for name in media_failures)
            elif not verification.get("verified"):
                fail.append(f"{source_url}: content verification failed")
                if logger:
                    logger.log(
                        "ERROR",
                        sync_stage,
                        **log_ctx,
                        error_code="feishu_verify_failed",
                        message=f"content verification failed: {verification}",
                        artifact_path=str(batch_dir / "feishu_sync_report.json"),
                        source_url=source_url,
                        doc_id=doc_id,
                    )
                item_report["status"] = "verify_failed"
            elif expected_images > 0 and fetched_images < expected_images:
                item_report["status"] = "ok-content-images-mismatch"
                fail.append(
                    f"{source_url}: image count mismatch (expected>={expected_images}, fetched={fetched_images})"
                )
            else:
                item_report["status"] = "ok"
            item_success += 1
            sync_items.append(item_report)
        except Exception as e:
            fail.append(f"{source_url}: {type(e).__name__}")
            if logger:
                logger.log(
                    "ERROR",
                    sync_stage,
                    **log_ctx,
                    error_code="sync_execute_exception",
                    message=f"{type(e).__name__}: {e}",
                    artifact_path=str(batch_dir / "feishu_sync_report.json"),
                    source_url=source_url,
                )
            item_report["status"] = f"failed({type(e).__name__})"
            sync_items.append(item_report)

    index_reports = sync_feishu_folder_indexes(
        sync_items,
        items if isinstance(items, list) else [],
        cfg,
        batch_dir,
        out_root,
        script_path,
        sync_dir,
        logger=logger,
        batch_id=batch_id,
        sync_stage=sync_stage,
    )

    save_feishu_folder_cache(folder_cache_path, folder_cache)
    report_status = "DRY_RUN" if not cfg.execute_feishu else ("PASS" if not fail else "PARTIAL")
    if logger:
        level = "INFO" if report_status in {"PASS", "DRY_RUN"} else "ERROR"
        logger.log(
            level,
            sync_stage,
            batch_id=batch_id,
            message="sync_complete",
            status=report_status,
            success=item_success,
            total=total,
            fail_count=len(fail),
            artifact_path=str(batch_dir / "feishu_sync_report.json"),
        )
    report = {
        "status": report_status,
        "strategy": "drive+import",
        "feishu_doc_root_mode": getattr(cfg, "feishu_doc_root_mode", "agent-docs-folder"),
        "total": total,
        "success": item_success,
        "fail": fail,
        "items": sync_items,
        "script": str(script_path),
        "sync_timeout": cfg.sync_timeout,
        "command_file": str(script_path),
        "payload_dir": str(sync_dir),
        "folder_cache": str(folder_cache_path),
        "index_cache": str(out_root / FEISHU_INDEX_CACHE_NAME),
        "feishu_folder_index": str(out_root / FEISHU_FOLDER_INDEX_NAME),
        "folder_indexes": index_reports,
        "media_upload_count": media_upload_count,
    }
    report_path = batch_dir / "feishu_sync_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anthropic docs/news pipeline")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-items", type=int, default=0, help="Limit for smoke-run/validation")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--resume-output", action="store_true", help="Allow writing into an output root that already has batch directories")
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
        choices=["agent-docs-folder", "parent"],
        default=os.environ.get("FEISHU_DOC_ROOT_MODE", "agent-docs-folder"),
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

    args = parser.parse_args()
    args.no_qa = args.no_qa or (not args.qa)
    return args


def discover_only(cfg: argparse.Namespace) -> Dict[str, object]:
    targets = build_targets(cfg)
    if cfg.max_items > 0:
        targets = targets[: cfg.max_items]
    out = Path(cfg.output_root) / "discover.json"
    Path(cfg.output_root).mkdir(parents=True, exist_ok=True)
    payload = {"count": len(targets), "items": targets}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
            "overall_status": "FAIL",
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
        fetched = sum(1 for it in batch_items if isinstance(it, dict) and it.get("status") == "fetched")
        logger.log(
            "INFO",
            "crawl",
            batch_id=batch_name,
            message="batch_crawl_complete",
            items_fetched=fetched,
            items_total=item_total,
        )
        manifest = write_batch(batch_items, batch_dir, cfg, logger=logger)

        qa_ok = manifest.get("qa", {}).get("qa_status") == "PASS"
        if cfg.commit and (qa_ok or cfg.force_commit):
            committed = commit_batch(batch_dir)
            manifest["git_commit"] = committed
            (batch_dir / "batch_qa_report.json").write_text(
                json.dumps({**manifest.get("qa", {}), "git_commit": committed}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif cfg.commit and not qa_ok:
            manifest["git_commit"] = False
            (batch_dir / "batch_qa_report.json").write_text(
                json.dumps({**manifest.get("qa", {}), "git_commit": False, "reason": "blocked_by_qa"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        if cfg.sync_feishu:
            sync_report = sync_to_feishu(manifest, cfg, batch_dir, out_root, logger=logger)
            manifest["feishu"] = sync_report
            if sync_report.get("status") in {"FAIL", "PARTIAL", "BLOCKED"}:
                manifest.setdefault("qa", {}).setdefault("errors", []).append(
                    f"feishu_sync_{sync_report.get('status')}: {sync_report.get('reason', '')}"
                )
                (batch_dir / "batch_qa_report.json").write_text(
                    json.dumps(manifest.get("qa", {}), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        manifest["batch_dir"] = str(batch_dir)
        (batch_dir / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        batches.append(manifest)

    failed_batches = []
    for batch in batches:
        qa_status = batch.get("qa", {}).get("qa_status")
        feishu_status = batch.get("feishu", {}).get("status")
        if qa_status not in {"PASS", "SKIPPED"}:
            failed_batches.append(batch.get("batch_id"))
        if feishu_status in {"FAIL", "PARTIAL", "BLOCKED"}:
            failed_batches.append(batch.get("batch_id"))

    summary = {
        "output_root": str(out_root),
        "target_count": len(targets),
        "batch_count": len(batches),
        "overall_status": "FAIL" if failed_batches else "PASS",
        "failed_batches": sorted(set(str(x) for x in failed_batches if x)),
        "items": all_items,
    }
    summary_path = out_root / "pipeline_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.log(
        "INFO" if summary["overall_status"] == "PASS" else "ERROR",
        "discover",
        message="pipeline_complete",
        overall_status=summary["overall_status"],
        batch_count=summary["batch_count"],
        failed_batches=summary["failed_batches"],
        artifact_path=str(summary_path),
    )
    return summary


def main() -> None:
    cfg = parse_args()
    if cfg.discover_only or os.environ.get("ANTHROPIC_PIPELINE_DISCOVER_ONLY"):
        print(json.dumps(discover_only(cfg), ensure_ascii=False, indent=2))
        return
    report = run_pipeline(cfg)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("overall_status") != "PASS" and not cfg.allow_failures:
        sys.exit(1)


def _self_test_feishu_paths() -> None:
    """Inline checks for folder mapping (no network)."""
    cfg_folder = argparse.Namespace(feishu_doc_root_mode="agent-docs-folder")
    cfg_parent = argparse.Namespace(feishu_doc_root_mode="parent")
    url = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
    segs_folder = feishu_folder_segments(url, "platform_docs", cfg_folder)
    full_folder = feishu_full_folder_path(segs_folder, cfg_folder)
    expected_tail = "anthropic-docs/Anthropic/Developer-docs/agents-and-tools/agent-skills"
    assert full_folder == f"agent-docs/{expected_tail}", full_folder
    assert segs_folder == expected_tail.split("/"), segs_folder
    segs_parent = feishu_folder_segments(url, "platform_docs", cfg_parent)
    assert feishu_full_folder_path(segs_parent, cfg_parent) == f"agent-docs/{expected_tail}"
    assert VENDOR_LIBRARIES["anthropic"]["status"] == "active"
    for name in ("openai", "gemini", "cursor"):
        assert VENDOR_LIBRARIES[name]["status"] == "reserved"
    blog_url = "https://claude.com/blog/some-post"
    blog_segs = feishu_folder_segments(blog_url, "", cfg_folder)
    assert "Claude" in blog_segs and "Blog" in blog_segs
    assert feishu_full_folder_path(blog_segs, cfg_folder).startswith(f"{AGENT_DOCS_ROOT}/")
    sample_index = build_folder_index_markdown(
        f"{AGENT_DOCS_ROOT}/anthropic-docs/Anthropic/Developer-docs/agents-and-tools/agent-skills",
        [
            {
                "title": "技能编写最佳实践",
                "source_url": url,
                "selected_url": url,
                "doc_url": "https://my.feishu.cn/docx/abc123",
                "published_at": "2026-05-22T00:00:00+00:00",
                "status": "ok-dry-run",
            }
        ],
    )
    assert "| 标题 | 原文链接 | 发布时间 | 飞书文档 | 状态 |" in sample_index
    assert FEISHU_INDEX_DOC_TITLE in sample_index


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test-feishu-paths":
        _self_test_feishu_paths()
        print("[OK] feishu path self-test passed")
    else:
        main()
