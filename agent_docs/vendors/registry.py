from __future__ import annotations

from typing import Dict

from agent_docs.core.config import DEFAULT_VENDOR

VENDOR_LIBRARIES: Dict[str, Dict[str, str]] = {
    "anthropic": {
        "status": "active",
        "feishu_root": "anthropic-docs",
        "brand_root": "Anthropic",
        "artifact_root": "artifacts/anthropic-content",
        "pipeline": "scripts/anthropic_content_pipeline.py",
    },
    "openai": {
        "status": "reserved",
        "feishu_root": "openai-docs",
        "brand_root": "OpenAI",
        "artifact_root": "artifacts/openai-content",
        "pipeline": "",
    },
    "gemini": {
        "status": "reserved",
        "feishu_root": "gemini-docs",
        "brand_root": "Gemini",
        "artifact_root": "artifacts/gemini-content",
        "pipeline": "",
    },
    "cursor": {
        "status": "reserved",
        "feishu_root": "cursor-docs",
        "brand_root": "Cursor",
        "artifact_root": "artifacts/cursor-content",
        "pipeline": "",
    },
}


def get_vendor_entry(vendor: str = DEFAULT_VENDOR) -> Dict[str, str]:
    return VENDOR_LIBRARIES.get(vendor, VENDOR_LIBRARIES[DEFAULT_VENDOR])


def feishu_library_root(vendor: str = DEFAULT_VENDOR) -> str:
    return get_vendor_entry(vendor)["feishu_root"]


def feishu_brand_root(vendor: str = DEFAULT_VENDOR) -> str:
    return get_vendor_entry(vendor)["brand_root"]


def artifact_root(vendor: str = DEFAULT_VENDOR) -> str:
    return get_vendor_entry(vendor)["artifact_root"]
