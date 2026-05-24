---
name: content-quality-gate
description: >-
  Performs Stage 1 content PASS spot-checks on crawled artifacts: structure
  fidelity, terminology preservation, source attribution, and image/table
  integrity. Use after batch QA PASS, for single-item verification, or when
  the user asks whether final markdown is publication-ready as source material.
---

# Content Quality Gate

Stage 1 控制平面 skill：**内容 PASS** 的人工/模型辅助审校，补充机器 QA。

## 何时使用

- Phase 2 single-item + QA PASS 后（Stage 1 完成声明必要条件之一）
- Phase 3 batch 完成后抽样
- 用户问「这篇译文/归档质量够不够」

## 前置

- 目标 batch 已有 artifacts：`batch_manifest.json`、`batch_qa_report.json`
- 机器门禁建议已 PASS：`qa_status`, `technical_status`, `content_status`（见 `agent_docs/qa/runner.py`）

## 抽样路径

典型 item 目录：

```text
artifacts/.../batch-NNN/NNN_<slug>/
  source.md
  final.zh.md | final.en.md
  images.json
  media/
```

## 审校清单

### 1. 来源与归因

- [ ] frontmatter / metadata 含 `source_url`、`published_at`（如有）
- [ ] 飞书 payload 会带可见归因块（`agent_docs/sinks/feishu.py`）；本地 `final.*.md` 亦应可追溯

### 2. 结构保真

- [ ] 标题层级与原文一致（H1–H6 不丢、不乱升/降级）
- [ ] 列表、表格、代码块、链接完整
- [ ] 机器 QA 计数不下降：`heading_count`, `table_count`, `link_count`, `image_count`（见 item dict / QA report）

### 3. 术语保留（中文输出）

以下英文术语**默认保留原文**，不强行中文化：

`Agent`, `Skill`, `Token`, `MCP`, `CLI`, `API`, `OAuth`, `JSON`, `Markdown`, `YAML`, `SDK`

（完整列表见 `AGENTS.md` / `TRANSLATE_PRESERVED_TERMS`。）

### 4. 图片与媒体

- [ ] `images.json` 中 `status: ok` 的条目在 `media/` 有对应文件
- [ ] markdown 中图片引用指向本地化路径或合理占位
- [ ] 接受 SVG/远程失败等已知限制，但需在 QA errors 中已解释

### 5. 语言策略

- 中文优先路径：`final.zh.md` 存在且可读
- 仅英文源且无翻译配置：`final.en.md` 可接受，但需在 review 中标注 `need_translate`

## 输出格式

```markdown
## Content Quality Gate

- **Verdict**: PASS | FAIL | PASS_WITH_NOTES
- **Sample**: `<source_url>` → `<final_path>`
- **Structure**: OK / issues (headings, tables, code blocks, links)
- **Terminology**: OK / violations (list terms wrongly translated)
- **Attribution**: OK / missing fields
- **Media**: OK / partial (list failed images)
- **Notes**: 非阻塞改进项
- **Evidence**: 引用的 QA 字段或文件路径
```

## 边界

- **不做**：修改 ingest 代码（除非 FAIL 且已确认是工具 bug）
- **不替代**：`qa-triage`（处理 QA FAIL）
- **不声明** Stage 1 完成，除非结合 workflow 中全部完成条件

## 参考

- `workflows/stage1_source_library.md` Phase 2、完成声明
- `agent_docs/qa/gates.py` — 机器门禁规则
- `DEBUG.md` — QA FAIL 场景
