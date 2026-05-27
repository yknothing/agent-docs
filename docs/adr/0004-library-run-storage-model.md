# ADR-0004: Library / Run 分离，替代 batch 目录作为存储语义

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: 产品/架构讨论（用户确认意图）
- **Related**: [ADR-0001](./0001-source-library-and-pluggable-delivery.md), [ADR-0003](./0003-multi-vendor-taxonomy-data-driven.md), [ADR-0005](./0005-artifacts-path-mapping-analysis.md), `agent_docs/cli/anthropic.py`, `agent_docs/ingest/process.py`

---

## Context

### 用户问题

> 至于你考虑的批次问题，是否有更优雅、聪明的实现方案？

### 当前 batch 模型

```
artifacts/anthropic-content/
  discover.json
  pipeline.log
  pipeline_summary.json
  batch-001/
    001_{slug}/
      source.md, final.{lang}.md, images.json, raw.html, media/
    batch_manifest.json
    batch_qa_report.json
    feishu_sync_commands.sh   # optional
  batch-002/
    ...
```

生成逻辑（`agent_docs/cli/anthropic.py`）：

- `batch_name = f"batch-{index // batch_size + 1:03d}"`
- item 目录：`f"{index:03d}_{safe_slug(source_url)}"`
- 已有 `batch-*` 且无 `--resume-output` → FAIL
- `--resume-output`：仅允许写入已有 output root，**不跳过** 已完成 batch → 有覆盖风险

### 问题清单

| 问题 | 说明 |
|------|------|
| 序号绑定 discover 顺序 | 重跑 discover 后 `001_` 前缀可能对应不同 URL |
| batch = **存储** 单位 | 语义是「跑批分组」，不是「资料库条目」 |
| slug vs title | 本地用 URL slug；飞书叶子用 doc title（双轨认知） |
| resume 模糊 | 无法「只重跑 FAIL 且 source 未变的 doc」 |
| 多厂商 | 靠不同 `--output-root` 手工区分，无统一 library 范式 |
| QA 分组 | batch-size 20 仅为运维；与 Library 生命周期无关 |

Stage 1 目标是 **Source Library**，不是「batch 归档」；batch 应降级为 **Run 内的并行/QA 分片**，而非目录主键。

---

## Decision

### 1. Run / Library 分离

```text
artifacts/
  library/                          # canonical，长期存在
    {vendor}/
      index.json                    # 全库索引：doc_id, source_url, taxonomy_path, qa_status, paths...
      {doc_id}/                     # doc_id = stable slug 或 normalized url hash
        source.md
        final.{lang}.md             # 仍只写一个 final（见 ADR-0005）
        images.json
        media/
        meta.json                   # source_url, selected_url, published_at, versions...
        raw.html                    # 可选保留策略

  runs/
    {run_id}/                       # 单次 pipeline 执行，可 GC
      discover.json
      pipeline.log
      pipeline_summary.json
      qa_report.json                # 本次 touched doc_ids + PASS/FAIL
      delivery/
        {sink}/
          sync_report.json
```

### 2. 稳定主键 `doc_id`

- 由 **normalized `source_url`** 生成（现有 `safe_slug()` 可演进为 canonical doc_id）。
- **不再** 使用全局序号前缀 `001_`、`002_` 作为目录名一部分。
- 同一 `doc_id` 重跑：**幂等覆盖** 或 **version 子目录**（`versions/20260527T120000/`），由 `meta.json` 指向 current version。

### 3. batch 的新语义

| 概念 | 新含义 |
|------|--------|
| `batch_size` | Run 内 **并行度 / QA 分组 / 日志分片**，不写进 library 路径 |
| `batch_qa_report` | 变为 `runs/{run_id}/qa_report.json` 中的 **section** 或按 chunk 的文件 |
| `--batch-size 20` | 保留 CLI 参数，仅影响 **执行调度**，不影响 storage layout |

### 4. Resume / 增量

- **`--skip-unchanged`**（目标 flag）：读 `library/{vendor}/index.json`，跳过 `source_url` + content hash 未变且 `qa_status=PASS` 的 doc。
- **`--only-failed`**：仅重跑 index 中 FAIL 或 missing 的 doc_id。
- 废弃或重定义 `--resume-output`：不再表示「往已有 batch 目录里写」。

### 5. 与 Delivery / Taxonomy

- Delivery adapter 读 **`library/index.json` + taxonomy**，不读 `batch_manifest.json`。
- `index.json` 条目含 `taxonomy_path`（由 ADR-0003 `resolve_taxonomy` 填充）。

---

## Consequences

### Positive

- 目录语义 = **资料库**，与产品目标一致。
- 续跑、增量、多 vendor 统一模型。
- LLM Wiki / 知识层可按 `taxonomy_path` 或 `doc_id` 挂载，无需解析 batch 序号。
- Git：可选只对 `library/` 子集 commit，runs 可 gitignore。

### Negative

- **Breaking layout change**：需 migration script（从现有 `batch-*` 导入 library）。
- 短期双写或兼容：manifest 格式下游（Feishu）需同步改。
- `index.json` 并发写需简单文件锁或 atomic write 规范。

### 对比表

| | 现在 | 目标（本 ADR） |
|--|------|----------------|
| 主键 | batch 序号 + index | `vendor + doc_id` |
| 跑批 | `batch-001/` 目录 | `runs/{run_id}/` 元数据 |
| 续跑 | `--resume-output` | index 驱动 `--skip-unchanged` |
| 多厂商 | 不同 output_root | `library/{vendor}/` |
| Delivery 输入 | `batch_manifest.json` | `library/index.json` |

---

## Alternatives considered

| 方案 | 未采纳原因 |
|------|------------|
| 保留 batch 目录，仅加 symlink 到 feishu_mirror | 双份路径维护，易 drift |
| 用 git submodule  per doc | 过重，不适合数千篇 |
| 纯 object store（S3）无本地 tree | Stage 1 需本地 QA、git 可选 commit artifacts |
| 仅去掉 `001_` 前缀，保留 batch-* | batch 仍非 library 语义，resume 问题仍在 |

---

## Migration outline（实现时）

1. 工具：`scripts/migrate_batch_to_library.py` — 扫描 `batch-*/**`, 写入 `library/{vendor}/{doc_id}/`, 生成 index。
2. 双跑期：pipeline 同时写 old batch（deprecated）与 library，QA 以 library 为准。
3. 切换 Feishu adapter 读 index。
4. 文档与 npm 默认 output 指向 `artifacts/library/anthropic`。
5. 移除 batch 存储路径（major version / CHANGELOG）。

---

## Open questions

- `raw.html` 是否对所有 source 永久保留，还是仅 news / 失败诊断保留？（现状：全写；见 ADR-0005）
- version 子目录 vs 原地覆盖：默认 **原地覆盖** + `meta.json` 记录 `last_run_id`，version 目录仅 `--keep-history` 时启用。
