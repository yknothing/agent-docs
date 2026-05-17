#!/usr/bin/env python3
from __future__ import annotations

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
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


UA = "Mozilla/5.0 (compatible; AnthropicContentPipeline/1.0)"
DEFAULT_BATCH_SIZE = 20
DEFAULT_TRANSLATE_TIMEOUT = 120
DEFAULT_OUTPUT_ROOT = "artifacts/anthropic-content"


ALLOWED_SITEMAP_PREFIXES = {
    "news",
    "research",
    "engineering",
    "learn",
    "economic-futures",
    "system-cards",
}

PLATFORM_DOCS_URL = "https://platform.claude.com/llms.txt"
CODE_DOCS_URL = "https://code.claude.com/docs/llms.txt"
SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"

IMAGE_EXTS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".svg",
    ".webp",
}


ALLOWED_DOC_HOSTS = {
    "platform.claude.com",
    "code.claude.com",
}

NEWS_HOSTS = {
    "www.anthropic.com",
    "anthropic.com",
}


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


def safe_slug(url: str, max_len: int = 120) -> str:
    p = urllib.parse.urlparse(url)
    slug = p.path.strip("/").replace("/", "__")
    if not slug:
        slug = "index"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug)
    if len(slug) > max_len:
        suffix = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug[: max_len - 9]}_{suffix}"
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
    return text and count / max(1, len(text)) > 0.005


def chinese_ratio(text: str) -> float:
    if not text:
        return 0.0
    count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return count / max(1, len(text))


def strip_frontmatter(markdown_text: str) -> str:
    if not markdown_text.startswith("---"):
        return markdown_text
    parts = markdown_text.split("---", 2)
    if len(parts) == 3:
        return parts[2].strip()
    return markdown_text


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
        return "utf-8"
    m = re.search(r"charset=([A-Za-z0-9_-]+)", content_type, flags=re.IGNORECASE)
    if not m:
        if "text/" in content_type:
            return "utf-8"
        return "utf-8"
    return m.group(1)


def http_get(url: str, timeout: int = 30) -> Tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            body = resp.read()
        except http.client.IncompleteRead as e:
            body = e.partial
        ctype = resp.headers.get("Content-Type", "")
        charset = parse_charset(ctype)
        text = body.decode(charset, errors="replace")
        return resp.status, ctype, text


def http_get_bytes(url: str, timeout: int = 30) -> Tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            data = resp.read()
        except http.client.IncompleteRead as e:
            data = e.partial
        ctype = resp.headers.get("Content-Type", "")
        return resp.status, ctype, data


def fetch_url(url: str, timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
    if not url:
        return None, None
    for attempt in range(3):
        try:
            status, content_type, text = http_get(url, timeout=timeout)
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if location:
                    return fetch_url(urllib.parse.urljoin(url, location), timeout=timeout)
            if e.code and 400 <= e.code < 500:
                return None, None
            if attempt == 2:
                return None, None
            time.sleep(1 + attempt)
        except Exception:
            if attempt == 2:
                return None, None
            time.sleep(1 + attempt)
    if status != 200:
        return None, None
    if content_type:
        return text, content_type
    return text, "text/plain"


def fetch_bytes(url: str, timeout: int = 30) -> Tuple[Optional[bytes], Optional[str]]:
    if not url:
        return None, None
    for attempt in range(3):
        try:
            status, content_type, data = http_get_bytes(url, timeout=timeout)
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if location:
                    return fetch_bytes(urllib.parse.urljoin(url, location), timeout=timeout)
            if e.code and 400 <= e.code < 500:
                return None, None
            if attempt == 2:
                return None, None
            time.sleep(1 + attempt)
        except Exception:
            if attempt == 2:
                return None, None
            time.sleep(1 + attempt)
    if status != 200:
        return None, None
    return data, content_type


def extract_links_from_llms(url: str) -> List[str]:
    text, _ = fetch_url(url) if url else (None, None)
    if not text:
        return []
    links = set()
    links.update(re.findall(r"https?://[^\s\)\]]+", text))
    links.update(re.findall(r"\[[^\]]*?\]\((https?://[^\)\s]+)\)", text))
    cleaned = []
    seen = set()
    for link in links:
        normalized = normalize_link(link)
        if not normalized:
            continue
        p = urllib.parse.urlparse(normalized)
        if p.path in {"", "/"}:
            continue
        if p.netloc in ALLOWED_DOC_HOSTS and "/docs/" not in p.path:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def discover_news_urls(
    sitemap_url: str = SITEMAP_URL,
    allowed_prefixes: Optional[Sequence[str]] = None,
) -> List[str]:
    if allowed_prefixes is None:
        allowed_prefixes = sorted(ALLOWED_SITEMAP_PREFIXES)
    text, _ = fetch_url(sitemap_url)
    if not text:
        return []
    raw_urls = re.findall(r"<loc>(.*?)</loc>", text)
    out: List[str] = []
    allowed = {str(prefix).strip("/").lower() for prefix in allowed_prefixes if str(prefix).strip("/")}
    for u in raw_urls:
        u = u.strip()
        p = urllib.parse.urlparse(u)
        if p.scheme not in {"http", "https"}:
            continue
        if p.netloc.lower() not in NEWS_HOSTS:
            continue
        segs = [s for s in p.path.strip("/").split("/") if s]
        if not segs:
            continue
        first = segs[0].lower()
        if first in allowed:
            out.append(urllib.parse.urlunparse((
                p.scheme.lower(),
                p.netloc.lower(),
                re.sub(r"/+$", "", p.path),
                "",
                "",
                "",
            )))
    return sorted(set(out))


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
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    proc = subprocess.run(
        ["html2text", "--pd", "--unicode-snob", "--no-wrap-links", "--images-as-html", "--skip-internal-links"],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def extract_title_from_markdown(markdown_text: str) -> str:
    for line in markdown_text.splitlines()[:40]:
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


def extract_images(markdown_text: str, base_url: str) -> List[Tuple[str, str]]:
    urls: List[Tuple[str, str]] = []
    seen = set()
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text):
        src = normalize_url(base_url, m.group(1).strip())
        if src not in seen:
            seen.add(src)
        urls.append((src, m.group(0)))
    for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", markdown_text, re.IGNORECASE):
        src = normalize_url(base_url, m.group(1).strip())
        if src not in seen:
            seen.add(src)
        urls.append((src, m.group(0)))
    # keep deterministic and dedup by URL
    dedup: List[Tuple[str, str]] = []
    seen = set()
    for src, marker in urls:
        if src in seen:
            continue
        seen.add(src)
        dedup.append((src, marker))
    return dedup


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
    return ".bin"


def download_images(image_refs: List[Tuple[str, str]], out_dir: Path) -> List[Dict[str, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, str]] = []
    for src, original in image_refs:
        if not src or src.startswith("data:") or src.startswith("mailto:"):
            records.append({"source": src, "file": "", "status": "skip-unsupported"})
            continue
        data, ctype = fetch_bytes(src, timeout=30)
        if not data:
            records.append({"source": src, "file": "", "status": "failed-fetch"})
            continue
        sha = hashlib.sha1((src + original).encode("utf-8")).hexdigest()[:12]
        ext = infer_image_ext(ctype or "", src)
        out_file = out_dir / f"{sha}{ext}"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if not out_file.exists():
            out_file.write_bytes(data)
        records.append({"source": src, "file": str(out_file), "status": "ok", "marker": original})
    return records


def rewrite_image_links(markdown_text: str, image_records: List[Dict[str, str]]) -> str:
    valid_records = [
        rec
        for rec in image_records
        if rec.get("status") == "ok" and rec.get("source") and rec.get("file")
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


def build_translate_prompt(title: str, source_url: str, text: str) -> str:
    return (
        "你是高级技术翻译与技术写作助手。请将以下英文技术文档翻译为地道中文。"
        "要求：\n"
        "1) 完整保留原文 Markdown 结构（标题、列表、代码块、链接、表格、引用、任务列表、图片占位）。\n"
        "2) 不添加未出现的技术事实。\n"
        "3) 表格、链接、图片语法与占位符保持可识别结构。\n"
        "4) 标题优先使用原文口吻与术语。\n\n"
        f"文档标题: {title or 'Untitled'}\n"
        f"来源: {source_url}\n\n{text}"
    )


def call_translator(text: str, title: str, source_url: str, cfg: argparse.Namespace) -> Tuple[str, str]:
    mode = cfg.translate_mode
    if not cfg.translate:
        return text, "skipped(translate-disabled)"
    if mode == "off":
        return text, "skipped(no-translator)"
    if mode == "auto":
        if os.environ.get("LANGCRAFT_CMD"):
            mode = "command"
        elif os.environ.get("OPENAI_API_KEY"):
            mode = "openai"
        else:
            return text, "skipped(no-translator-config)"
    if mode == "command":
        cmd = os.environ.get("LANGCRAFT_CMD")
        if not cmd:
            return text, "failed(no-LANGCRAFT_CMD)"
        try:
            p = subprocess.run(
                cmd,
                shell=True,
                input=text,
                text=True,
                capture_output=True,
                timeout=cfg.translate_timeout,
            )
            if p.returncode == 0 and p.stdout:
                return p.stdout.strip(), "ok(command:LANGCRAFT_CMD)"
            return text, f"failed(cmd:{p.returncode})"
        except Exception as e:
            return text, f"failed(cmd-exception:{type(e).__name__})"
    if mode == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return text, "failed(no-OPENAI_API_KEY)"
        api_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1/chat/completions")
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是中文技术文档翻译助手。请仅返回翻译结果，不要输出额外说明。",
                },
                {
                    "role": "user",
                    "content": build_translate_prompt(title, source_url, text),
                },
            ],
            "temperature": 0.1,
        }
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=cfg.translate_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                translated = data["choices"][0]["message"]["content"].strip()
                return translated, "ok(openai)"
        except Exception as e:
            return text, f"failed(openai:{type(e).__name__})"
    return text, f"skipped(unsupported:{mode})"


def pick_preferred_source_url(source_url: str) -> Tuple[str, bool]:
    if not source_url:
        return source_url, False
    if "/zh-CN/" in source_url or re.search(r"/zh(?:-CN)?/", source_url):
        return source_url, True
    if not re.search(r"/en(?:-[A-Za-z]{2})?/", source_url):
        return source_url, False
    zh_candidate = re.sub(r"/en(?:-[A-Za-z]{2})?/", "/zh-CN/", source_url, count=1)
    has_zh = test_source_available(zh_candidate)
    if has_zh:
        return zh_candidate, True
    zh_candidate = re.sub(r"/en(?:-[A-Za-z]{2})?/", "/zh/", source_url, count=1)
    has_zh = test_source_available(zh_candidate)
    if has_zh:
        return zh_candidate, True
    return source_url, False


def test_source_available(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        if e.code in {405, 501}:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return 200 <= resp.status < 300
            except Exception:
                return False
        return False
    except Exception:
        return False


def write_metadata_block(meta: Dict[str, object]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            esc = str(v).replace("\"", '\\"')
            lines.append(f'{k}: "{esc}"')
    lines.append("---\n")
    return "\n".join(lines)


def build_targets(cfg: argparse.Namespace) -> List[Dict[str, str]]:
    targets: List[Dict[str, str]] = []
    if cfg.include_platform_docs:
        for u in extract_links_from_llms(PLATFORM_DOCS_URL):
            targets.append({"source_type": "platform_docs", "source_url": u, "seed_url": PLATFORM_DOCS_URL})
    if cfg.include_code_docs:
        for u in extract_links_from_llms(CODE_DOCS_URL):
            targets.append({"source_type": "claude_code_docs", "source_url": u, "seed_url": CODE_DOCS_URL})
    if cfg.include_news:
        for u in discover_news_urls(allowed_prefixes=cfg.allowed_news_prefixes):
            targets.append({"source_type": "anthropic_news", "source_url": u, "seed_url": SITEMAP_URL})
    seen = set()
    unique = []
    for t in targets:
        key = normalize_url_path(t["source_url"]) or t["source_url"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    return sorted(unique, key=lambda x: (x["source_type"], x["source_url"]))


def process_target(target: Dict[str, str], cfg: argparse.Namespace, batch_dir: Path, index: int) -> Dict[str, object]:
    source_url = target["source_url"]
    source_type = target["source_type"]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    slug = safe_slug(source_url)
    item_dir = batch_dir / f"{index:03d}_{slug}"
    item_dir.mkdir(parents=True, exist_ok=True)
    media_dir = item_dir / "media"
    title = safe_slug(source_url)

    selected_url = source_url
    has_zh_version = False
    if source_type != "anthropic_news":
        selected_url, has_zh_version = pick_preferred_source_url(source_url)

    raw_content, raw_ct = fetch_url(selected_url)
    if has_zh_version and is_not_found_text(raw_content or "", extract_title(raw_content or "")):
        selected_url = source_url
        has_zh_version = False
        raw_content, raw_ct = fetch_url(selected_url)
    raw_source = selected_url
    status = "fetched" if raw_content else "failed-fetch"

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

        # fallback title from markdown heading, then URL basename
        parsed_title = extract_title_from_markdown(raw_markdown)
        if parsed_title:
            title = parsed_title
        if not title:
            title = Path(urllib.parse.urlparse(raw_source).path).name or safe_slug(source_url)

    if not raw_markdown or is_not_found_text(raw_markdown, title) or visible_content_len(raw_markdown) < 20:
        status = "failed-empty-or-not-found"

    source_lang = "zh" if has_chinese(raw_markdown) else "en"
    source_image_refs = extract_images(raw_markdown, raw_source)
    images = download_images(source_image_refs, media_dir)
    raw_markdown_local_images = rewrite_image_links(raw_markdown, images)

    need_translate = source_lang != "zh" and not has_zh_version and cfg.translate
    if need_translate:
        translated_markdown, translator_note = call_translator(raw_markdown_local_images, title, source_url, cfg)
    else:
        translated_markdown = raw_markdown_local_images
        translator_note = (
            "skipped(no-translate-needed)" if (source_lang == "zh" or has_zh_version)
            else "skipped(translate-disabled)"
        )

    final_lang = "zh" if (need_translate and translator_note.startswith("ok")) or source_lang == "zh" else "en"
    final_markdown = translated_markdown
    if need_translate and translator_note.startswith("ok") and not has_chinese(final_markdown):
        translator_note = f"{translator_note};failed-language-check"
        final_lang = "en"

    table_source = count_tables(raw_markdown)
    table_output = count_tables(final_markdown)
    heading_source = count_headings(raw_markdown)
    heading_output = count_headings(final_markdown)
    link_source = count_links(raw_markdown)
    link_output = count_links(final_markdown)

    media_manifest = item_dir / "images.json"
    media_manifest.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    source_file = item_dir / "source.md"
    final_file = item_dir / f"final.{final_lang}.md"
    raw_file = item_dir / "raw.html"

    source_meta = {
        "title": title or "Untitled",
        "source_type": source_type,
        "source_url": source_url,
        "selected_url": selected_url,
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
        "need_translate": need_translate,
        "has_local_images": all(
            image.get("status") == "ok"
            and image.get("file")
            and f"media/{Path(str(image.get('file'))).name}" in final_markdown
            for image in images
        ) if images else False,
        "media_manifest": str(media_manifest),
    }
    source_file.write_text(write_metadata_block(source_meta) + "\n" + raw_markdown, encoding="utf-8")
    final_file.write_text(write_metadata_block(final_meta) + "\n" + final_markdown, encoding="utf-8")
    raw_file.write_text(raw_content or "", encoding="utf-8")

    return {
        "status": status,
        "source_type": source_type,
        "title": title or "Untitled",
        "source_url": source_url,
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


def run_qa(manifest: Dict[str, object]) -> Dict[str, object]:
    cfg = manifest.get("config", {})
    if isinstance(cfg, dict) and cfg.get("skip_qa"):
        return {"qa_status": "SKIPPED", "checked_items": len(manifest.get("items", [])), "errors": []}

    items = manifest.get("items", [])
    passed = True
    missing: List[str] = []
    errors: List[str] = []
    image_delta = 0
    table_delta = 0
    heading_delta = 0
    link_delta = 0

    for it in items:
        if not isinstance(it, dict):
            continue
        source_url = str(it.get("source_url"))
        if it.get("status") != "fetched":
            passed = False
            errors.append(f"not_fetched: {source_url}")
        src_path = Path(str(it.get("source_path", "")))
        out_path = Path(str(it.get("final_path", "")))
        if not src_path.exists() or not out_path.exists():
            passed = False
            missing.append(source_url)
            continue
        out_text = out_path.read_text(encoding="utf-8", errors="replace")
        if visible_content_len(out_text) < 20:
            passed = False
            errors.append(f"empty_or_too_short_output: {source_url}")
        if is_not_found_text(out_text, str(it.get("title", ""))):
            passed = False
            errors.append(f"not_found_output: {source_url}")
        if not isinstance(it.get("image_count_source"), int):
            passed = False
            errors.append(f"bad_image_count_source: {source_url}")
        if not isinstance(it.get("table_count_source"), int):
            passed = False
            errors.append(f"bad_table_count_source: {source_url}")
        image_delta += int(it.get("image_count_output", 0)) - int(it.get("image_count_source", 0))
        table_delta += int(it.get("table_count_output", 0)) - int(it.get("table_count_source", 0))
        heading_delta += int(it.get("heading_count_output", 0)) - int(it.get("heading_count_source", 0))
        link_delta += int(it.get("link_count_output", 0)) - int(it.get("link_count_source", 0))

        if int(it.get("image_count_output", 0)) < int(it.get("image_count_source", 0)):
            passed = False
            errors.append(f"image_count_decrease: {source_url}")
        if int(it.get("table_count_output", 0)) < int(it.get("table_count_source", 0)):
            passed = False
            errors.append(f"table_count_decrease: {source_url}")
        if int(it.get("heading_count_output", 0)) < int(it.get("heading_count_source", 0)):
            passed = False
            errors.append(f"heading_count_decrease: {source_url}")
        if int(it.get("link_count_output", 0)) < int(it.get("link_count_source", 0)):
            passed = False
            errors.append(f"link_count_decrease: {source_url}")
        for image in it.get("images", []):
            if not isinstance(image, dict):
                continue
            if image.get("status") != "ok":
                passed = False
                errors.append(f"image_download_failed: {source_url} -> {image.get('source')}")
                continue
            image_file = Path(str(image.get("file", "")))
            if not image_file.is_file():
                passed = False
                errors.append(f"image_file_missing: {source_url} -> {image_file}")
            if image_file.name and f"media/{image_file.name}" not in out_text:
                passed = False
                errors.append(f"image_not_localized: {source_url} -> {image_file.name}")
        if it.get("need_translate") and not it.get("final_language") == "zh":
            passed = False
            errors.append(f"translate_missing: {source_url}")
        if it.get("final_language") == "zh" and chinese_ratio(out_text) < 0.005:
            passed = False
            errors.append(f"zh_output_language_check_failed: {source_url}")

    return {
        "qa_status": "PASS" if passed else "FAIL",
        "checked_items": len(items),
        "image_count_delta": image_delta,
        "table_count_delta": table_delta,
        "heading_count_delta": heading_delta,
        "link_count_delta": link_delta,
        "missing_files": missing,
        "errors": errors,
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def write_batch(batch_items: List[Dict[str, object]], batch_dir: Path, cfg: argparse.Namespace) -> Dict[str, object]:
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
        manifest["qa"] = run_qa(manifest)
    else:
        manifest["qa"] = {"qa_status": "SKIPPED", "checked_items": len(batch_items), "errors": []}
    (batch_dir / "batch_qa_report.json").write_text(
        json.dumps(manifest["qa"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_path = batch_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
    candidates = re.finditer(r"\{.*?\}", text, flags=re.DOTALL)
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
        r"""(?:"document_id"\s*:\s*"([^"]+)"|\"document_id\"\s*:\s*'([^']+)'|document_id[:=]\s*([A-Za-z0-9_-]+)|doc(?:ument)?_id[:=]\s*([A-Za-z0-9_-]+))""",
        text,
    )
    for groups in regex_candidates:
        for value in groups:
            if value:
                return value
    url_candidate = re.search(r"https://[A-Za-z0-9./?=&_%#:-]*docs[A-Za-z0-9./?=&_%#:-]*", text)
    if url_candidate:
        return url_candidate.group(0)
    return None


def sync_to_feishu(manifest: Dict[str, object], cfg: argparse.Namespace, batch_dir: Path, out_root: Path) -> Dict[str, object]:
    if not cfg.sync_feishu:
        return {"status": "SKIPPED", "reason": "sync-feishu-disabled"}
    out_root = out_root.resolve()
    batch_dir = batch_dir.resolve()
    qa_status = manifest.get("qa", {}).get("qa_status")
    if qa_status != "PASS" and not cfg.force_sync:
        return {"status": "BLOCKED", "reason": f"qa_status={qa_status}", "items": []}

    folder_token = cfg.feishu_folder_token or os.environ.get("FEISHU_DOC_FOLDER_TOKEN")
    if cfg.execute_feishu and not folder_token:
        return {"status": "FAIL", "reason": "FEISHU_DOC_FOLDER_TOKEN missing"}
    lark_cli = shutil.which("lark-cli")
    if cfg.execute_feishu and not lark_cli:
        return {"status": "FAIL", "reason": "lark-cli not installed"}

    token_placeholder = folder_token or "${FEISHU_DOC_FOLDER_TOKEN}"

    items = manifest.get("items", [])
    total = len(items)
    ok = 0
    fail: List[str] = []
    media_upload_count = 0
    item_success = 0
    sync_items: List[Dict[str, object]] = []
    script_path = batch_dir / "feishu_sync_commands.sh"
    script_content = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"cd {shlex.quote(str(out_root))}",
        "",
        'if [ -z "${FEISHU_DOC_FOLDER_TOKEN:-}" ]; then',
        '  echo "env FEISHU_DOC_FOLDER_TOKEN required for execution. Using placeholder in commands."',
        "fi",
        "",
    ]
    script_path.write_text(
        "\n".join(script_content) + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    sync_dir = batch_dir / "sync_payload"
    sync_dir.mkdir(parents=True, exist_ok=True)

    for it in items:
        if not isinstance(it, dict):
            continue
        source_url = str(it.get("source_url"))
        title = str(it.get("title", source_url))
        final_path = Path(str(it.get("final_path", "")))
        source_type = str(it.get("source_type", ""))
        slug = str(it.get("slug", safe_slug(source_url)))
        media_items = it.get("images", [])
        if not final_path.exists():
            fail.append(f"{source_url}: final path missing")
            continue

        content_rel = str(final_path.resolve().relative_to(out_root.resolve()))
        create_cmd = [
            "lark-cli",
            "docs",
            "+create",
            "--api-version",
            "v2",
            "--title",
            title,
            "--content",
            f"@{content_rel}",
        ]
        create_cmd.extend(["--folder-token", token_placeholder])

        payload_file = sync_dir / f"{slug}-payload.md"
        if not payload_file.exists():
            payload_file.write_text(final_path.read_text(encoding="utf-8"), encoding="utf-8")
        create_cmd[create_cmd.index("--content") + 1] = f"@{payload_file.relative_to(out_root)}"

        create_cmd_str = " ".join(shlex.quote(x) for x in create_cmd)
        with script_path.open("a", encoding="utf-8") as sf:
            sf.write(f"{create_cmd_str}\n")

        item_report: Dict[str, object] = {
            "source_url": source_url,
            "title": title,
            "create_command": create_cmd_str,
            "status": "pending",
            "doc_id": None,
            "media_upload_count": 0,
            "media_uploads": [],
        }

        if not cfg.execute_feishu:
            planned_media = 0
            for image in media_items:
                if not isinstance(image, dict):
                    continue
                image_file = image.get("file", "")
                if not image_file:
                    continue
                image_path = Path(image_file)
                if not image_path.is_file():
                    continue
                media_upload_cmd = [
                    "lark-cli",
                    "docs",
                    "+media-insert",
                    "--doc",
                    "<DOC_ID_OR_URL_FROM_CREATE>",
                    "--file",
                    f"{image_path.resolve().relative_to(out_root)}",
                    "--type",
                    "image",
                ]
                media_cmd_str = " ".join(shlex.quote(x) for x in media_upload_cmd)
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{media_cmd_str}\n")
                item_report["media_uploads"].append(media_cmd_str)
                planned_media += 1
            item_report["media_upload_count"] = planned_media
            sync_items.append(item_report)
            item_report["status"] = "ok-dry-run"
            item_success += 1
            ok += 1
            continue

        try:
            proc = subprocess.run(
                create_cmd,
                cwd=str(out_root),
                check=False,
                capture_output=True,
                text=True,
                timeout=cfg.sync_timeout,
            )
            if proc.returncode != 0:
                fail.append(f"{source_url}: create failed({proc.returncode})")
                item_report["status"] = f"create_failed({proc.returncode})"
                sync_items.append(item_report)
                continue
            out = proc.stdout.strip()
            doc_id = parse_doc_id_from_output(out)
            if not doc_id:
                item_report["status"] = "create_no_doc_id"
                sync_items.append(item_report)
                fail.append(f"{source_url}: create succeeded but no doc_id")
                continue
            item_report["doc_id"] = doc_id
            item_media_uploaded = 0
            media_upload_succeeded = True
            for image in media_items:
                if not isinstance(image, dict):
                    continue
                image_file = image.get("file", "")
                if not image_file:
                    continue
                image_path = Path(image_file)
                if not image_path.is_file():
                    continue
                media_upload_cmd = [
                    "lark-cli",
                    "docs",
                    "+media-insert",
                    "--doc",
                    doc_id or "<DOC_ID>",
                    "--file",
                    f"{image_path.resolve().relative_to(out_root)}",
                    "--type",
                    "image",
                ]
                media_cmd_str = " ".join(shlex.quote(x) for x in media_upload_cmd)
                with script_path.open("a", encoding="utf-8") as sf:
                    sf.write(f"{media_cmd_str}\n")
                item_report["media_uploads"].append(media_cmd_str)
                media_proc = subprocess.run(
                    media_upload_cmd,
                    cwd=str(out_root),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=cfg.sync_timeout,
                )
                if media_proc.returncode != 0:
                    media_upload_succeeded = False
                    fail.append(f"{source_url}: media-upload failed")
                    item_report["status"] = f"media_upload_failed({media_proc.returncode})"
                    break
                media_upload_count += 1
                item_media_uploaded += 1
                item_report["media_upload_count"] = item_media_uploaded
            if media_upload_succeeded:
                item_report["status"] = "ok"
                item_success += 1
                item_report["media_upload_count"] = item_media_uploaded
            sync_items.append(item_report)
        except Exception as e:
            fail.append(f"{source_url}: {type(e).__name__}")
            item_report["status"] = f"failed({type(e).__name__})"
            sync_items.append(item_report)

    report = {
        "status": ("DRY_RUN" if not cfg.execute_feishu and not fail else ("PASS" if not fail else "PARTIAL")),
        "total": total,
        "success": item_success,
        "fail": fail,
        "items": sync_items,
        "script": str(script_path),
        "sync_timeout": cfg.sync_timeout,
        "command_file": str(script_path),
        "payload_dir": str(sync_dir),
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
    parser.add_argument("--sync-timeout", type=int, default=120)
    parser.add_argument("--feishu-folder-token", default="")

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
    batches: List[Dict[str, object]] = []
    all_items: List[Dict[str, object]] = []

    for batch_index in range(0, len(targets), cfg.batch_size):
        this_batch = targets[batch_index : batch_index + cfg.batch_size]
        batch_name = f"batch-{batch_index // cfg.batch_size + 1:03d}"
        batch_dir = out_root / batch_name
        batch_items: List[Dict[str, object]] = []
        for i, t in enumerate(this_batch):
            item = process_target(t, cfg, batch_dir, batch_index + i + 1)
            batch_items.append(item)
            all_items.append(item)
        manifest = write_batch(batch_items, batch_dir, cfg)

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
            sync_report = sync_to_feishu(manifest, cfg, batch_dir, out_root)
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


if __name__ == "__main__":
    main()
