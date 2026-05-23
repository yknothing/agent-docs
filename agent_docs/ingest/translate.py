"""Translation helpers and Chinese-first URL selection."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from typing import Tuple

from agent_docs.core.config import (
    DEFAULT_CHARSET,
    OPENAI_DEFAULT_API_BASE,
    OPENAI_DEFAULT_CHAT_MODEL,
    OPENAI_TRANSLATE_TEMPERATURE,
    TRANSLATE_PRESERVED_TERMS,
)
from agent_docs.ingest.fetch import test_source_available


def build_translate_prompt(title: str, source_url: str, text: str) -> str:
    return (
        "你是高级技术翻译与技术写作助手。请将以下英文技术文档翻译为地道中文。"
        "要求：\n"
        "1) 完整保留原文 Markdown 结构（标题、列表、代码块、链接、表格、引用、任务列表、图片占位）。\n"
        "2) 不添加未出现的技术事实。\n"
        "3) 表格、链接、图片语法与占位符保持可识别结构。\n"
        "4) 以下英文术语默认保留原文，不强行中文化："
        f"{TRANSLATE_PRESERVED_TERMS}。\n"
        "5) 译文要做到“信、达、雅”：信息准确、表达顺畅、中文自然可读。\n"
        "6) 若配置了 LangCraft 翻译/审校 skill，优先遵循其术语表与风格约束。\n\n"
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
        api_url = os.environ.get("OPENAI_API_BASE", OPENAI_DEFAULT_API_BASE)
        model = os.environ.get("OPENAI_CHAT_MODEL", OPENAI_DEFAULT_CHAT_MODEL)
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
            "temperature": OPENAI_TRANSLATE_TEMPERATURE,
        }
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode(DEFAULT_CHARSET),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=cfg.translate_timeout) as resp:
                data = json.loads(resp.read().decode(DEFAULT_CHARSET, errors="replace"))
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
