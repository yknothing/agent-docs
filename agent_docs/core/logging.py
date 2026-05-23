from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from agent_docs.core.config import LOG_SECRET_KEY_FRAGMENTS


class PipelineLogger:
    """Append-only JSON-lines logger at {output_root}/pipeline.log."""

    def __init__(self, out_root: Path) -> None:
        self.out_root = out_root.resolve()
        self.log_path = self.out_root / "pipeline.log"
        self.out_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize(value: object) -> object:
        if isinstance(value, str):
            return re.sub(r"(Bearer\s+)\S+", r"\1[REDACTED]", value, flags=re.IGNORECASE)
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
            **self._sanitize(fields),
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
