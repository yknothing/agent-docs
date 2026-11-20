# ADR-0003: 多厂商从一开始——数据驱动 Taxonomy，Delivery 共用

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: 产品/架构讨论（用户确认意图）
- **Related**: [ADR-0001](./0001-source-library-and-pluggable-delivery.md), [ADR-0004](./0004-library-run-storage-model.md), `agent_docs/vendors/registry.py`, `agent_docs/sinks/feishu.py`, `ARCHITECTURE.md` Known Limitations

---

## Context

### 用户声明

> 我建议一开始就为多厂商做准备，以简化映射逻辑。

### 现状

`VENDOR_LIBRARIES`（`agent_docs/vendors/registry.py`）已注册四厂商，但：

| 已接线 | 未接线 / 硬编码 |
|--------|-----------------|
| `feishu_library_root(vendor)` / `feishu_brand_root(vendor)` | CLI 默认 `--output-root` 仍 `DEFAULT_OUTPUT_ROOT`，**未调用** `artifact_root(vendor)` |
| 飞书 path 前缀两段 | `feishu_folder_segments()` 内 **Anthropic 域名与 category 全硬编码** |
| artifact 目录名预留 | 无 OpenAI/Gemini/Cursor pipeline |

`ARCHITECTURE.md` Known Limitations 已记录：

> `feishu_folder_segments` 硬编码 vendor 分支 → 多厂商扩展时需要修改函数本体

每新增 vendor 或调整 URL 规则都要 **改 Python 函数**，映射逻辑无法共享给 Notion / Wiki，与 ADR-0001 冲突。

### 目标

- **一个 vendor 一份 source + taxonomy 配置**，而非一份 Feishu 函数。
- **Taxonomy 输出** 被 Library、Feishu、Notion、Wiki **共同消费**。
- 新 vendor onboarding = 加配置 + discover 规则 + QA 样本，而非 fork `feishu_folder_segments`。

---

## Decision

### 1. 三层分离

```text
Layer A — Vendor Source Rules（每厂商一份 YAML/JSON）
  hosts, url_patterns, discover 策略, 语言策略, excluded_paths

Layer B — Canonical Taxonomy（跨 Delivery 共用）
  category tree: e.g. Developer-docs/agents-and-tools/agent-skills
  函数: resolve_taxonomy(vendor, source_url) -> category_segments[]

Layer C — Delivery Mapping（每 channel 一份）
  feishu:  vault_root + segment_naming + doc_title rules + import strategy
  notion:  database_id + property mapping
  wiki:    path_template + frontmatter schema
```

**关键**：Layer B 的输入是 `source_url`，输出是 **与渠道无关** 的分类路径；Layer C 只负责「如何把 B + Library 条目投影到渠道」。

### 2. 配置布局（目标态）

```text
configs/
  vendors/
    anthropic/
      sources.yaml      # Layer A
      taxonomy.yaml     # Layer B rules
    openai/
      sources.yaml
      taxonomy.yaml
    ...
  delivery/
    feishu.yaml         # Layer C for Feishu
    notion.yaml         # reserved
    wiki.yaml           # reserved
```

### 3. Registry 演进

```python
# 目标字段（概念）
VENDOR_LIBRARIES = {
    "anthropic": {
        "status": "active",
        "library_root": "artifacts/library/anthropic",
        "brand_root": "Anthropic",
        "sources_config": "configs/vendors/anthropic/sources.yaml",
        "taxonomy_config": "configs/vendors/anthropic/taxonomy.yaml",
        "pipeline": "scripts/anthropic_content_pipeline.py",
    },
    ...
}
```

- **删除** registry 级 `feishu_root`；Feishu vault 内库名移至 `configs/delivery/feishu.yaml`（如 `anthropic-docs` 段）。

### 4. 从 `feishu_folder_segments` 迁移

1. 将现有 host → category 表 **原样抽取** 到 `taxonomy.yaml`（行为不变，先测试锁定）。
2. `feishu_folder_segments(url)` → `resolve_taxonomy(vendor, url)` + `feishu_adapter.segments(taxonomy)`。
3. 保留 `tests/test_feishu_folder_segments.py` 作为 **行为契约**，直到等价新测试覆盖后改名。

### 5. CLI

- 所有 pipeline 入口支持 **`--vendor anthropic`**（默认）。
- `library_root`、`taxonomy_config` 从 registry 解析，禁止 hardcode `artifacts/anthropic-content` 为唯一根。

---

## Consequences

### Positive

- 新 vendor = 新配置目录 + discover 插件，**不** 复制 800 行 Feishu 函数。
- Notion/Wiki adapter 与 Feishu **共享 taxonomy**，映射逻辑简化。
- 单测可对 YAML fixture 做 table-driven 测试，优于巨型 Python if/elif。

### Negative

- 一次性迁移成本：抽 YAML + 双跑测试。
- 需定义 taxonomy rule DSL（host prefix、path strip、category_map）并文档化。

### Stage 2 关系

Stage 2 **横向主题 taxonomy**（AI Coding、MCP 等）为 **overlay**，不替代 Layer B 的「来源站点语义分类」；可在 `meta.json` 增加 `themes[]` 字段。

---

## Alternatives considered

| 方案 | 未采纳原因 |
|------|------------|
| 每 vendor 复制 `feishu_folder_segments` 分支 | 映射逻辑 N 倍膨胀 |
| 仅 registry 加 openai 条目，规则仍写 Python | 不解决硬编码本质 |
| 统一到单一全球 taxonomy 树、无 vendor 配置 | 各厂商 URL 结构差异大，一层规则难表达 |

---

## Acceptance criteria（实现时）

- [ ] Anthropic 现有 Feishu 路径单测 **全部 PASS**（行为回归）。
- [ ] 新增 vendor 只需添加 `configs/vendors/{name}/` 与 registry 行，**无需** 修改 `feishu.py` 内 URL 解析。
- [ ] `resolve_taxonomy` 被 Library index 与至少一个 Delivery adapter 调用。
