"""Distribution sinks (Feishu and future channels)."""

from agent_docs.sinks.feishu import (
    build_folder_index_markdown,
    feishu_full_folder_path,
    feishu_folder_segments,
    run_feishu_path_self_test,
    sync_to_feishu,
)

__all__ = [
    "build_folder_index_markdown",
    "feishu_full_folder_path",
    "feishu_folder_segments",
    "run_feishu_path_self_test",
    "sync_to_feishu",
]
