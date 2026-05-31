"""Per-item QA gate checks."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from agent_docs.core.config import (
    CHINESE_RATIO_THRESHOLD,
    CRAWL_STATUS_FETCHED,
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
from agent_docs.ingest.normalize import chinese_ratio, is_content_too_short, is_not_found_text


def run_technical_qa_item(it: Dict[str, object], out_text: str) -> Tuple[List[str], Dict[str, int]]:
    """Return technical QA errors and structure deltas for one manifest item."""
    source_url = str(it.get("source_url"))
    errors: List[str] = []
    deltas = {
        "image_count_delta": 0,
        "table_count_delta": 0,
        "heading_count_delta": 0,
        "link_count_delta": 0,
    }

    if it.get("status") != CRAWL_STATUS_FETCHED:
        errors.append(f"{QA_ERR_NOT_FETCHED}: {source_url}")

    src_path = Path(str(it.get("source_path", "")))
    out_path = Path(str(it.get("final_path", "")))
    if not src_path.exists() or not out_path.exists():
        return errors, deltas

    if is_content_too_short(out_text):
        errors.append(f"{QA_ERR_EMPTY_OR_TOO_SHORT}: {source_url}")
    if is_not_found_text(out_text, str(it.get("title", ""))):
        errors.append(f"{QA_ERR_NOT_FOUND_OUTPUT}: {source_url}")
    if not isinstance(it.get("image_count_source"), int):
        errors.append(f"{QA_ERR_BAD_IMAGE_COUNT_SOURCE}: {source_url}")
    if not isinstance(it.get("table_count_source"), int):
        errors.append(f"{QA_ERR_BAD_TABLE_COUNT_SOURCE}: {source_url}")

    if isinstance(it.get("image_count_source"), int):
        deltas["image_count_delta"] = int(it.get("image_count_output", 0)) - int(it.get("image_count_source", 0))
        if int(it.get("image_count_output", 0)) < int(it.get("image_count_source", 0)):
            errors.append(f"{QA_ERR_IMAGE_COUNT_DECREASE}: {source_url}")
    if isinstance(it.get("table_count_source"), int):
        deltas["table_count_delta"] = int(it.get("table_count_output", 0)) - int(it.get("table_count_source", 0))
        if int(it.get("table_count_output", 0)) < int(it.get("table_count_source", 0)):
            errors.append(f"{QA_ERR_TABLE_COUNT_DECREASE}: {source_url}")
    if isinstance(it.get("heading_count_source"), int):
        deltas["heading_count_delta"] = int(it.get("heading_count_output", 0)) - int(it.get("heading_count_source", 0))
        if int(it.get("heading_count_output", 0)) < int(it.get("heading_count_source", 0)):
            errors.append(f"{QA_ERR_HEADING_COUNT_DECREASE}: {source_url}")
    if isinstance(it.get("link_count_source"), int):
        deltas["link_count_delta"] = int(it.get("link_count_output", 0)) - int(it.get("link_count_source", 0))
        if int(it.get("link_count_output", 0)) < int(it.get("link_count_source", 0)):
            errors.append(f"{QA_ERR_LINK_COUNT_DECREASE}: {source_url}")

    for image in it.get("images", []):
        if not isinstance(image, dict):
            continue
        if image.get("status") != IMAGE_STATUS_OK:
            errors.append(f"{QA_ERR_IMAGE_DOWNLOAD_FAILED}: {source_url} -> {image.get('source')}")
            continue
        image_file = Path(str(image.get("file", "")))
        if not image_file.is_file():
            errors.append(f"{QA_ERR_IMAGE_FILE_MISSING}: {source_url} -> {image_file}")
        if image_file.name and f"media/{image_file.name}" not in out_text:
            errors.append(f"{QA_ERR_IMAGE_NOT_LOCALIZED}: {source_url} -> {image_file.name}")

    return errors, deltas


def run_content_qa_item(it: Dict[str, object], out_text: str) -> List[str]:
    """Return content QA errors for one manifest item."""
    source_url = str(it.get("source_url"))
    errors: List[str] = []

    if it.get("need_translate") and not it.get("final_language") == "zh":
        errors.append(f"{QA_ERR_TRANSLATE_MISSING}: {source_url}")
    if it.get("final_language") == "zh" and chinese_ratio(out_text) < CHINESE_RATIO_THRESHOLD:
        errors.append(f"{QA_ERR_ZH_LANGUAGE_CHECK}: {source_url}")

    return errors
