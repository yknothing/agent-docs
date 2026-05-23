"""Source URL discovery from llms.txt and sitemap feeds."""

from __future__ import annotations

import argparse
import re
import urllib.parse
from typing import Dict, List, Optional, Sequence

from agent_docs.core.config import (
    ALLOWED_DOC_HOSTS,
    ALLOWED_SITEMAP_PREFIXES,
    CODE_DOCS_URL,
    NEWS_HOSTS,
    PLATFORM_DOCS_URL,
    SITEMAP_URL,
)
from agent_docs.ingest.fetch import fetch_url
from agent_docs.ingest.normalize import normalize_link, normalize_url_path


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
    if getattr(cfg, "target_urls", None):
        target_urls = [str(u).strip() for u in cfg.target_urls if str(u).strip()]
        if target_urls:
            target_set = set(target_urls)
            targets = [t for t in targets if t["source_url"] in target_set]
    seen = set()
    unique = []
    for t in targets:
        key = normalize_url_path(t["source_url"]) or t["source_url"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    return sorted(unique, key=lambda x: (x["source_type"], x["source_url"]))
