"""URL, markdown, and text normalization utilities."""

from __future__ import annotations

import datetime
import html as html_lib
import json
import re
import shutil
import subprocess
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import hashlib
import urllib.parse

from agent_docs.core.config import (
    ALLOWED_DOC_HOSTS,
    CHINESE_RATIO_THRESHOLD,
    DEFAULT_CHARSET,
    DEFAULT_SLUG_MAX_LEN,
    HTML_NEWLINE_COLLAPSE_MIN,
    MIN_VISIBLE_CONTENT_LEN,
    SLUG_HASH_SUFFIX_LEN,
    TITLE_SCAN_MAX_LINES,
)


def normalize_url_path(url: str) -> Optional[str]:
    if not url:
        return None
    p = urllib.parse.urlparse(url)
    if p.scheme not in {"http", "https"}:
        return None
    normalized = p._replace(fragment="", query="")
    normalized = normalized._replace(path=re.sub(r"/+$", "", normalized.path))
    return urllib.parse.urlunparse(normalized)


def normalize_link(raw_url: str) -> Optional[str]:
    if not raw_url:
        return None
    cleaned = raw_url.strip().strip("()<>`\"'")
    if not cleaned:
        return None
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc and cleaned.startswith("/"):
        return None
    if not parsed.scheme:
        return None
    if parsed.path in {"", "/"}:
        return None
    if parsed.netloc.lower() not in ALLOWED_DOC_HOSTS:
        return None
    if parsed.netloc in ALLOWED_DOC_HOSTS and "/docs/" not in parsed.path:
        return None
    return normalize_url_path(cleaned)


def safe_slug(url: str, max_len: int = DEFAULT_SLUG_MAX_LEN) -> str:
    p = urllib.parse.urlparse(url)
    slug = p.path.strip("/").replace("/", "__")
    if not slug:
        slug = "index"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug)
    if len(slug) > max_len:
        suffix = hashlib.sha1(url.encode("utf-8")).hexdigest()[:SLUG_HASH_SUFFIX_LEN]
        slug = f"{slug[: max_len - SLUG_HASH_SUFFIX_LEN - 1]}_{suffix}"
    return slug


def normalize_url(base: str, url: str) -> str:
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return urllib.parse.urljoin(base, url)


def has_chinese(text: str) -> bool:
    count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return bool(text) and count / max(1, len(text)) > CHINESE_RATIO_THRESHOLD


def chinese_ratio(text: str) -> float:
    if not text:
        return 0.0
    count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return count / max(1, len(text))


def detect_source_language_by_url(url: str) -> str:
    if not url:
        return "unknown"
    path = urllib.parse.urlparse(url).path.lower()
    if re.search(r"/zh(?:-[a-z]{2})?/", path):
        return "zh"
    if re.search(r"/en(?:-[a-z]{2})?/", path):
        return "en"
    return "unknown"


def normalize_publication_time(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", html_lib.unescape(str(raw)).strip())
    if not text:
        return ""

    candidates: List[str] = [text]
    candidates.extend(re.findall(r"(20\d{2}-\d{2}-\d{2}T[^ \t\n]+)", text))
    candidates.extend(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", text))
    candidates.extend(re.findall(r"\b20\d{2}/\d{2}/\d{2}\b", text))
    candidates.extend(re.findall(r"\b\d{1,2} [A-Za-z]{3,9} 20\d{2}\b", text))

    seen = set()
    for cand in candidates:
        if not cand:
            continue
        if cand in seen:
            continue
        seen.add(cand)
        for s in (cand, cand.replace("Z", "+00:00")):
            try:
                dt = datetime.datetime.fromisoformat(s)
                return dt.replace(tzinfo=dt.tzinfo or datetime.timezone.utc).isoformat()
            except Exception:
                pass
        try:
            dt = parsedate_to_datetime(cand)
            if dt:
                return dt.astimezone(datetime.timezone.utc).isoformat()
        except Exception:
            pass
        for fmt in ("%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.datetime.strptime(cand, fmt)
                return dt.date().isoformat()
            except Exception:
                pass
    return ""


def _extract_publication_time_from_json(data: object, keys: Sequence[str], out: List[str]) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            lk = str(k).lower()
            if isinstance(v, str) and any(key in lk for key in keys):
                out.append(v)
            if isinstance(v, (dict, list)):
                _extract_publication_time_from_json(v, keys, out)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _extract_publication_time_from_json(item, keys, out)


def extract_publication_time(raw_html: str, markdown_text: str = "") -> str:
    candidates: List[str] = []

    if raw_html:
        for tag in re.finditer(r"<meta[^>]+>", raw_html, flags=re.IGNORECASE):
            attr = tag.group(0)
            key_match = re.search(r"(?:property|name|itemprop)\s*=\s*['\"]([^'\"]+)['\"]", attr, flags=re.IGNORECASE)
            value_match = re.search(r"(?:content|value)\s*=\s*['\"]([^'\"]+)['\"]", attr, flags=re.IGNORECASE)
            if key_match and value_match:
                key = key_match.group(1).lower()
                if any(word in key for word in ("publish", "date", "time")):
                    candidates.append(value_match.group(1))

        for tag in re.finditer(r"<time[^>]+datetime\s*=\s*['\"]([^'\"]+)['\"]", raw_html, re.IGNORECASE):
            candidates.append(tag.group(1))

        for m in re.finditer(
            r"<script[^>]+type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            block = m.group(1).strip()
            if not block:
                continue
            try:
                payload = json.loads(block)
            except Exception:
                continue
            _extract_publication_time_from_json(
                payload,
                ("date", "published", "modified", "created", "upload"),
                candidates,
            )

    meta, _ = parse_frontmatter(markdown_text)
    if isinstance(meta, dict):
        for key in ("date", "datePublished", "published_at", "pubDate", "publishDate"):
            val = meta.get(key)
            if isinstance(val, str) and val.strip():
                candidates.append(val)

    for raw in candidates:
        normalized = normalize_publication_time(raw)
        if normalized:
            return normalized
    return ""


def strip_frontmatter(markdown_text: str) -> str:
    _, body = parse_frontmatter(markdown_text)
    return body


def parse_frontmatter(markdown_text: str) -> Tuple[Dict[str, object], str]:
    if not markdown_text.startswith("---"):
        return {}, markdown_text
    parts = markdown_text.split("---", 2)
    if len(parts) != 3:
        return {}, markdown_text
    meta: Dict[str, object] = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1].replace('\\"', '"')
        elif val in ("true", "false"):
            val = val == "true"
        else:
            try:
                val = int(val) if "." not in val else float(val)
            except ValueError:
                pass
        meta[key] = val
    return meta, parts[2].strip()


def visible_content_len(markdown_text: str) -> int:
    body = strip_frontmatter(markdown_text)
    body = re.sub(r"```[\s\S]*?```", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", body)
    body = re.sub(r"\[[^\]]*\]\([^)]+\)", "", body)
    body = re.sub(r"[\s#|:`*_>-]+", "", body)
    return len(body)


def is_not_found_text(text: str, title: Optional[str] = None) -> bool:
    if not text:
        return True
    if title is None:
        title = extract_title(text)
    if not title:
        return False
    lower = title.lower()
    return "not found" in lower or "404" in lower


def looks_markdown(url: str, content_type: str, text: str) -> bool:
    ct = content_type.lower()
    if "text/markdown" in ct or url.endswith(".md"):
        return True
    if text.lstrip().startswith("<HomePage") and url.endswith(".md"):
        return True
    return False


def parse_charset(content_type: str) -> str:
    if not content_type:
        return DEFAULT_CHARSET
    m = re.search(r"charset=([A-Za-z0-9_-]+)", content_type, flags=re.IGNORECASE)
    if not m:
        if "text/" in content_type:
            return DEFAULT_CHARSET
        return DEFAULT_CHARSET
    return m.group(1)


def extract_main_article_html(html: str) -> str:
    m = re.search(r"<article[\s\S]*?</article>", html, re.IGNORECASE)
    if m:
        return m.group(0)
    m = re.search(r"<main[\s\S]*?</main>", html, re.IGNORECASE)
    if m:
        return m.group(0)
    return html


def html_to_markdown(html: str) -> str:
    if not html:
        return ""
    if shutil.which("html2text") is None:
        text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</(p|div|h\d|li|tr)>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        return re.sub(rf"\n{{{HTML_NEWLINE_COLLAPSE_MIN},}}", "\n\n", text).strip()
    proc = subprocess.run(
        ["html2text", "--unicode-snob", "--no-wrap-links", "--images-as-html", "--no-skip-internal-links"],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout.strip()
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|h\d|li|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(rf"\n{{{HTML_NEWLINE_COLLAPSE_MIN},}}", "\n\n", text).strip()


def extract_title_from_markdown(markdown_text: str) -> str:
    for line in markdown_text.splitlines()[:TITLE_SCAN_MAX_LINES]:
        m = re.match(r"^#\s+(\S.*)$", line.strip())
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def extract_title(html_or_markdown: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html_or_markdown, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return extract_title_from_markdown(html_or_markdown)


def count_tables(markdown_text: str) -> int:
    lines = markdown_text.splitlines()
    count = 0
    i = 0
    while i < len(lines) - 1:
        l1 = lines[i].strip()
        l2 = lines[i + 1].strip()
        if re.match(r"^\|.*\|$", l1) and re.match(r"^\|[\s\-\:\|]+$", l2):
            count += 1
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
        else:
            i += 1
    return count


def count_headings(markdown_text: str) -> int:
    return sum(1 for line in markdown_text.splitlines() if re.match(r"^#{1,6}\s+", line.strip()))


def count_links(markdown_text: str) -> int:
    total = len(re.findall(r"\[[^\]]*\]\([^)]+\)", markdown_text))
    total += len(re.findall(r"<a[^>]+href=[\"'][^\"']+[\"'][^>]*>", markdown_text, flags=re.IGNORECASE))
    return total


def is_content_too_short(markdown_text: str) -> bool:
    return visible_content_len(markdown_text) < MIN_VISIBLE_CONTENT_LEN
