"""YAML frontmatter metadata block writer."""

from __future__ import annotations

from typing import Dict


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
