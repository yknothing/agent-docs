"""Per-target crawl, normalize, translate, and artifact write."""

from __future__ import annotations

import argparse
import datetime
import json
import urllib.parse
from pathlib import Path
from typing import Dict, Optional

from agent_docs.core.config import (
    CRAWL_STATUS_FAILED_EMPTY,
    CRAWL_STATUS_FAILED_FETCH,
    CRAWL_STATUS_FETCHED,
    DEFAULT_CHARSET,
    FETCH_RETRY_COUNT_LOG,
    IMAGE_STATUS_OK,
    IMAGE_STATUS_SKIP,
    ITEM_DIR_INDEX_WIDTH,
)
from agent_docs.core.logging import PipelineLogger
from agent_docs.ingest.fetch import fetch_url
from agent_docs.ingest.media import download_images, extract_images, rewrite_image_links
from agent_docs.ingest.metadata import write_metadata_block
from agent_docs.ingest.normalize import (
    chinese_ratio,
    count_headings,
    count_links,
    count_tables,
    detect_source_language_by_url,
    extract_main_article_html,
    extract_publication_time,
    extract_title,
    extract_title_from_markdown,
    has_chinese,
    html_to_markdown,
    is_content_too_short,
    is_not_found_text,
    looks_markdown,
    safe_slug,
    visible_content_len,
)
from agent_docs.ingest.translate import call_translator, pick_preferred_source_url


def process_target(
    target: Dict[str, str],
    cfg: argparse.Namespace,
    batch_dir: Path,
    index: int,
    *,
    logger: Optional[PipelineLogger] = None,
    batch_id: str = "",
    item_index: int = 0,
    item_total: int = 0,
) -> Dict[str, object]:
    source_url = target["source_url"]
    source_type = target["source_type"]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    slug = safe_slug(source_url)
    item_dir = batch_dir / f"{index:0{ITEM_DIR_INDEX_WIDTH}d}_{slug}"
    item_dir.mkdir(parents=True, exist_ok=True)
    media_dir = item_dir / "media"
    title = safe_slug(source_url)
    log_ctx = {"batch_id": batch_id, "item_index": item_index, "item_total": item_total, "source_url": source_url}

    source_language_hint = detect_source_language_by_url(source_url)
    selected_url = source_url
    has_zh_version = False
    if source_type != "anthropic_news":
        if source_language_hint == "en":
            selected_url = source_url
        else:
            selected_url, has_zh_version = pick_preferred_source_url(source_url)

    raw_content, raw_ct = fetch_url(selected_url)
    if has_zh_version and is_not_found_text(raw_content or "", extract_title(raw_content or "")):
        if logger:
            logger.log(
                "WARN",
                "crawl",
                url=selected_url,
                error_code="zh_fallback",
                message="Chinese URL not found; falling back to original",
                **log_ctx,
            )
        selected_url = source_url
        has_zh_version = False
        raw_content, raw_ct = fetch_url(selected_url)
    raw_source = selected_url
    status = CRAWL_STATUS_FETCHED if raw_content else CRAWL_STATUS_FAILED_FETCH
    if not raw_content and logger:
        logger.log(
            "ERROR",
            "crawl",
            url=selected_url,
            error_code="fetch_failed",
            message="HTTP fetch returned no content",
            retry_count=FETCH_RETRY_COUNT_LOG,
            artifact_path=str(item_dir),
            **log_ctx,
        )

    if source_type == "anthropic_news":
        raw_content, raw_ct = fetch_url(source_url)
        raw_source = source_url
        raw_markdown = ""
        title = extract_title(raw_content or "")
        if raw_content:
            raw_markdown = html_to_markdown(extract_main_article_html(raw_content))
    else:
        if raw_content and looks_markdown(selected_url, raw_ct or "", raw_content):
            raw_markdown = raw_content.strip()
            title = extract_title(raw_markdown) or title
        elif raw_content:
            title = extract_title(raw_content)
            raw_markdown = html_to_markdown(extract_main_article_html(raw_content))
        else:
            raw_markdown = ""

        parsed_title = extract_title_from_markdown(raw_markdown)
        if parsed_title:
            title = parsed_title
        if not title:
            title = Path(urllib.parse.urlparse(raw_source).path).name or safe_slug(source_url)

    published_at = extract_publication_time(raw_content or "", raw_markdown)

    if not raw_markdown or is_not_found_text(raw_markdown, title) or is_content_too_short(raw_markdown):
        status = CRAWL_STATUS_FAILED_EMPTY

    if source_language_hint in {"zh", "en"}:
        source_lang = source_language_hint
    else:
        source_lang = "zh" if has_chinese(raw_markdown) else "en"
    source_image_refs = extract_images(raw_markdown, raw_source)
    images = download_images(source_image_refs, media_dir)
    if logger:
        for image in images:
            if image.get("status") not in {IMAGE_STATUS_OK, IMAGE_STATUS_SKIP}:
                logger.log(
                    "WARN",
                    "crawl",
                    url=str(image.get("source") or source_url),
                    error_code="image_download_failed",
                    message=f"image status={image.get('status')}",
                    artifact_path=str(item_dir / "images.json"),
                    **log_ctx,
                )
    raw_markdown_local_images = rewrite_image_links(raw_markdown, images)

    need_translate = source_lang == "en" and cfg.translate
    if need_translate:
        translated_markdown, translator_note = call_translator(raw_markdown_local_images, title, source_url, cfg)
    else:
        translated_markdown = raw_markdown_local_images
        translator_note = (
            "skipped(no-translate-needed)" if source_lang == "zh"
            else "skipped(translate-disabled)"
        )

    final_lang = "zh" if (need_translate and translator_note.startswith("ok")) or source_lang == "zh" else "en"
    final_markdown = translated_markdown
    if need_translate and translator_note.startswith("ok") and not has_chinese(final_markdown):
        translator_note = f"{translator_note};failed-language-check"
        final_lang = "en"
    if logger and need_translate and not translator_note.startswith("ok"):
        logger.log(
            "ERROR",
            "translate",
            url=source_url,
            error_code="translate_failed",
            message=translator_note,
            artifact_path=str(item_dir),
            **log_ctx,
        )

    table_source = count_tables(raw_markdown)
    table_output = count_tables(final_markdown)
    heading_source = count_headings(raw_markdown)
    heading_output = count_headings(final_markdown)
    link_source = count_links(raw_markdown)
    link_output = count_links(final_markdown)

    media_manifest = item_dir / "images.json"
    media_manifest.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding=DEFAULT_CHARSET)
    source_file = item_dir / "source.md"
    final_file = item_dir / f"final.{final_lang}.md"
    raw_file = item_dir / "raw.html"

    source_meta = {
        "title": title or "Untitled",
        "source_type": source_type,
        "source_url": source_url,
        "selected_url": selected_url,
        "published_at": published_at,
        "has_zh_version": has_zh_version,
        "source_language": source_lang,
        "captured_at_utc": now,
        "translator": translator_note,
        "is_translated": need_translate and translator_note.startswith("ok"),
        "image_count_source": len(source_image_refs),
        "image_count_output": len(extract_images(final_markdown, raw_source)),
        "visible_content_length": visible_content_len(final_markdown),
        "final_chinese_ratio": chinese_ratio(final_markdown),
        "table_count_source": table_source,
        "table_count_output": table_output,
        "heading_count_source": heading_source,
        "heading_count_output": heading_output,
        "link_count_source": link_source,
        "link_count_output": link_output,
    }
    final_meta = {
        **source_meta,
        "published_at": published_at,
        "need_translate": need_translate,
        "has_local_images": all(
            image.get("status") == IMAGE_STATUS_OK
            and image.get("file")
            and f"media/{Path(str(image.get('file'))).name}" in final_markdown
            for image in images
        ) if images else False,
        "media_manifest": str(media_manifest),
    }
    source_file.write_text(write_metadata_block(source_meta) + "\n" + raw_markdown, encoding=DEFAULT_CHARSET)
    final_file.write_text(write_metadata_block(final_meta) + "\n" + final_markdown, encoding=DEFAULT_CHARSET)
    raw_file.write_text(raw_content or "", encoding=DEFAULT_CHARSET)

    if logger:
        logger.log(
            "INFO",
            "crawl",
            url=source_url,
            message="item_complete",
            status=status,
            artifact_path=str(item_dir),
            **log_ctx,
        )

    return {
        "status": status,
        "source_type": source_type,
        "title": title or "Untitled",
        "source_url": source_url,
        "published_at": published_at,
        "selected_url": selected_url,
        "slug": slug,
        "has_zh_version": has_zh_version,
        "need_translate": need_translate,
        "translator": translator_note,
        "source_language": source_lang,
        "final_language": final_lang,
        "captured_at_utc": now,
        "source_path": str(source_file),
        "final_path": str(final_file),
        "media_manifest": str(media_manifest),
        "media_dir": str(media_dir),
        "image_count_source": len(source_image_refs),
        "image_count_output": len(extract_images(final_markdown, raw_source)),
        "visible_content_length": visible_content_len(final_markdown),
        "final_chinese_ratio": chinese_ratio(final_markdown),
        "table_count_source": table_source,
        "table_count_output": table_output,
        "heading_count_source": heading_source,
        "heading_count_output": heading_output,
        "link_count_source": link_source,
        "link_count_output": link_output,
        "images": images,
    }
