"""Append-only JSON-lines pipeline logger with secret scrubbing."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Callable, Pattern, Union

from agent_docs.core.config import LOG_SECRET_KEY_FRAGMENTS

_Replacement = Union[str, Callable[[re.Match[str]], str]]


def _redact_auth_assignment(m: re.Match[str]) -> str:
    k = m.group("k")
    eq = m.group("eq")
    if m.group("dv") is not None:
        return f'{k}{eq}"[REDACTED]"'
    if m.group("sv") is not None:
        return f"{k}{eq}'[REDACTED]'"
    return f"{k}{eq}[REDACTED]"


# Conservative, high-confidence secret patterns scanned in EVERY string value
# before the JSON line is written. We deliberately avoid generic "long random
# string" heuristics (e.g., `[A-Za-z0-9]{32,}`) to keep legitimate identifiers
# such as Feishu folder_token, doc_id hashes and content SHAs visible for
# debugging. The bar for redaction is: "this pattern is very likely a real
# credential leak in observed lark-cli / curl / openai outputs".
#
# Pattern ordering note:
# The HTTP-header-shaped pattern (`Authorization: Scheme value`) runs FIRST
# because it overlaps both the bare Bearer pattern and the generic
# authorization-assignment pattern. Consuming the whole header in one match
# keeps redacted output as a single `[REDACTED]` block instead of producing
# nested `[REDACTED] [REDACTED]` artefacts.
_SECRET_VALUE_PATTERNS: tuple[tuple[Pattern[str], _Replacement], ...] = (
    # `Authorization: Bearer xxx` (HTTP header shape). Must run before the
    # bare `Bearer\s+\S+` pattern to avoid double-redaction.
    (
        re.compile(
            r"\bAuthorization\s*:\s*(?:Bearer|Basic|Digest|Token)\s+\S+",
            re.IGNORECASE,
        ),
        "Authorization: [REDACTED]",
    ),
    # Authorization: Bearer xxx (case insensitive, value follows token)
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-+=/]+", re.IGNORECASE), "Bearer [REDACTED]"),
    # OpenAI / Anthropic style keys: sk-..., sk-ant-...
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b"), "sk-[REDACTED]"),
    # GitHub tokens: ghp_, gho_, ghu_, ghs_, ghr_
    (re.compile(r"\bgh[psour]_[A-Za-z0-9]{20,}\b"), "gh*_[REDACTED]"),
    # GitHub fine-grained PAT: github_pat_xxx
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_[REDACTED]"),
    # Feishu / Lark app secret style
    (re.compile(r"\bcli_[A-Za-z0-9]{10,}\b"), "cli_[REDACTED]"),
    # Generic URL credential query params: ?token=..., &access_token=..., etc.
    (
        re.compile(
            r"(?P<sep>[?&])(?P<k>token|secret|password|api[_-]?key|access[_-]?token|auth)"
            r"=(?P<v>[^&\s\"']+)",
            re.IGNORECASE,
        ),
        r"\g<sep>\g<k>=[REDACTED]",
    ),
    # `authorization` / `x-api-key` / `app_secret` assignment in free text.
    # Supports double-quoted, single-quoted, and unquoted values; quoted values
    # may contain whitespace (e.g., `Authorization="Basic dXNlcjpwYXNz"`).
    (
        re.compile(
            r"(?P<k>authorization|x-api-key|app[_-]?secret|api[_-]?secret)"
            r"(?P<eq>\s*[:=]\s*)"
            r"(?:"
            r"\"(?P<dv>[^\"]+)\""
            r"|'(?P<sv>[^']+)'"
            r"|(?P<uv>[A-Za-z0-9._\-+=/]+)"
            r")",
            re.IGNORECASE,
        ),
        _redact_auth_assignment,
    ),
)


def _scrub_string(value: str) -> str:
    out = value
    for pattern, replacement in _SECRET_VALUE_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


class PipelineLogger:
    """Append-only JSON-lines logger at ``{output_root}/pipeline.log``.

    Sanitization rules:

    * Dict keys whose lowercased name contains any fragment from
      ``LOG_SECRET_KEY_FRAGMENTS`` (``token``, ``secret``, ``password``,
      ``api_key``, ``authorization``, ``credential``) are DROPPED entirely.
    * Every remaining string value (top-level or nested in dict/list) is
      scanned by :data:`_SECRET_VALUE_PATTERNS` and matching substrings are
      replaced with ``[REDACTED]``. Non-secret content stays visible.
    """

    def __init__(self, out_root: Path) -> None:
        self.out_root = out_root.resolve()
        self.log_path = self.out_root / "pipeline.log"
        self.out_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize(value: object) -> object:
        if isinstance(value, str):
            return _scrub_string(value)
        if isinstance(value, dict):
            return {
                k: PipelineLogger._sanitize(v)
                for k, v in value.items()
                if not any(fragment in k.lower() for fragment in LOG_SECRET_KEY_FRAGMENTS)
            }
        if isinstance(value, list):
            return [PipelineLogger._sanitize(v) for v in value]
        return value

    def log(self, level: str, stage: str, **fields: object) -> None:
        record = {
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": level.upper(),
            "stage": stage,
            **self._sanitize(fields),  # type: ignore[arg-type]
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
