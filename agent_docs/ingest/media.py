"""Image extraction, download, and markdown link rewriting."""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

from agent_docs.core.config import (
    DEFAULT_IMAGE_EXT,
    DEFAULT_IMAGE_FETCH_TIMEOUT,
    IMAGE_EXTS,
    IMAGE_HASH_HEX_LEN,
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_OK,
    IMAGE_STATUS_SKIP,
)
from agent_docs.ingest.fetch import fetch_bytes
from agent_docs.ingest.normalize import normalize_url


def extract_images(markdown_text: str, base_url: str) -> List[Tuple[str, str]]:
    """Extract unique (resolved_src, original_marker) tuples from markdown text.

    Order is preserved (first occurrence wins). Both markdown ``![alt](src)``
    and raw ``<img src=...>`` are supported.
    """
    urls: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text):
        src = normalize_url(base_url, m.group(1).strip())
        if not src or src in seen:
            continue
        seen.add(src)
        urls.append((src, m.group(0)))
    for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", markdown_text, re.IGNORECASE):
        src = normalize_url(base_url, m.group(1).strip())
        if not src or src in seen:
            continue
        seen.add(src)
        urls.append((src, m.group(0)))
    return urls


def infer_image_ext(content_type: str, source_url: str) -> str:
    if source_url:
        ext = Path(urllib.parse.urlparse(source_url).path).suffix.lower()
        if ext in IMAGE_EXTS:
            return ext
    if content_type:
        if "image/" in content_type:
            cext = content_type.split(";", 1)[0].rsplit("/", 1)[-1].strip()
            if cext and f".{cext}" in IMAGE_EXTS:
                return f".{cext}"
        if "svg" in content_type:
            return ".svg"
    return DEFAULT_IMAGE_EXT


def download_images(image_refs: List[Tuple[str, str]], out_dir: Path) -> List[Dict[str, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, str]] = []
    for src, original in image_refs:
        if not src or src.startswith("data:") or src.startswith("mailto:"):
            records.append({"source": src, "file": "", "status": IMAGE_STATUS_SKIP})
            continue
        data, ctype = fetch_bytes(src, timeout=DEFAULT_IMAGE_FETCH_TIMEOUT)
        if not data:
            records.append({"source": src, "file": "", "status": IMAGE_STATUS_FAILED})
            continue
        sha = hashlib.sha1((src + original).encode("utf-8")).hexdigest()[:IMAGE_HASH_HEX_LEN]
        ext = infer_image_ext(ctype or "", src)
        out_file = out_dir / f"{sha}{ext}"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if not out_file.exists():
            out_file.write_bytes(data)
        records.append({"source": src, "file": str(out_file), "status": IMAGE_STATUS_OK, "marker": original})
    return records


def rewrite_image_links(markdown_text: str, image_records: List[Dict[str, str]]) -> str:
    valid_records = [
        rec
        for rec in image_records
        if rec.get("status") == IMAGE_STATUS_OK and rec.get("source") and rec.get("file")
    ]
    if not valid_records:
        return markdown_text

    out = markdown_text
    for rec in valid_records:
        marker = rec.get("marker", "")
        local_ref = f"media/{Path(rec['file']).name}"
        if marker and marker in out:
            if marker.startswith("!["):
                localized = re.sub(r"(!\[[^\]]*\]\()([^)]+)(\))", rf"\g<1>{local_ref}\g<3>", marker, count=1)
            else:
                localized = re.sub(r"src=[\"'][^\"']+[\"']", f'src="{local_ref}"', marker, count=1, flags=re.IGNORECASE)
            out = out.replace(marker, localized)

    mapping = {rec["source"]: f"media/{Path(rec['file']).name}" for rec in valid_records}

    def replace_md(m: re.Match[str]) -> str:
        src = normalize_url("", m.group(1).strip())
        if src in mapping:
            return m.group(0).replace(m.group(1).strip(), mapping[src])
        return m.group(0)

    def replace_html(m: re.Match[str]) -> str:
        src = m.group(1).strip()
        if src in mapping:
            return m.group(0).replace(src, mapping[src])
        return m.group(0)

    out = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", replace_md, out)
    out = re.sub(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", replace_html, out, flags=re.IGNORECASE)
    return out
