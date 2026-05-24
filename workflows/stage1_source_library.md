# Workflow: Stage 1 Source Library

> 控制平面 workflow。确定性动作由 tools（`agent_docs/cli/`、`scripts/anthropic_content_pipeline.py` 兼容入口）执行；开放性判断由 Agent Skills 承担。  
> 架构权威：`ARCHITECTURE.md` | Codex 入口：`docs/CODEX_GOAL.md`

## 目标

高质量收集、归档、完善 Anthropic（及后续厂商）官方开发资料源材料，产出可追溯 artifacts，并通过 **技术 PASS + 内容 PASS**。

**不是 Stage 1 目标**：深度分析、学习路径、商品化、Feishu 同步（除非用户明确要求分发验收）。

## 前置

- 仓库根目录 `agent-docs/`
- Python 3、npm
- 翻译（全量中文路径）：`LANGCRAFT_CMD` 或 `OPENAI_API_KEY`
- Feishu 支线（可选）：`FEISHU_DOC_FOLDER_TOKEN` + `lark-cli` user 登录

## 主线路径

```mermaid
flowchart LR
  P0[Phase 0 discover] --> P1[Phase 1 smoke]
  P1 --> P2[Phase 2 single + QA]
  P2 --> P3[Phase 3 batch + QA]
  P3 --> P4[Phase 4 translate 可选]
  P4 --> DONE[Stage 1 mainline PASS]
```

| Phase | 动作 | 工具命令 | 门禁 |
|:-----:|------|----------|------|
| 0 | 发现 URL 范围 | `npm run anthropic:discover` | `discover.json` 合理 |
| 1 | Smoke（无 QA/翻译） | `npm run anthropic:crawl:smoke` | `pipeline_summary` PASS |
| 2 | 单篇 + QA | `--max-items 1 --batch-size 1` | `batch_qa_report` PASS |
| 3 | 小批 + QA | `--batch-size 5`（或 5–10） | 每批 QA PASS |
| 4 | 启用翻译（需要时） | `--translate-mode auto` | QA PASS；API 限流监控 |

### Phase 0 — Discover

```bash
npm run anthropic:discover
# 检查 artifacts/anthropic-discovery/discover.json
```

**Skill 介入点**：`source-discovery` — 审阅 URL 范围是否覆盖目标开发文档，排除 courses 等 Stage 1 跳过项。

### Phase 1 — Smoke

```bash
npm run anthropic:crawl:smoke
```

验证抓取链路可用；**不**以 smoke 作为 Stage 1 完成标准。

### Phase 2 — Single item + QA

```bash
python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/stage1-verify \
  --translate-mode off
```

**PASS 条件**（技术 + 内容）：

- `batch_qa_report.json` → `qa_status: PASS`
- `source.md`、`final.*.md`、`images.json` 存在
- 图片本地化；结构计数不下降
- 来源 URL 可追溯（frontmatter / metadata）

**Skill 介入点**：`content-quality-gate` — 抽样对比 `source.md` 与 `final.zh.md`，确认结构保真、术语保留。

### Phase 3 — Batch + QA

```bash
python3 scripts/anthropic_content_pipeline.py \
  --batch-size 5 \
  --output-root artifacts/anthropic-content \
  --translate-mode off
# 或续跑：--resume-output
```

失败时 **Skill 介入点**：`qa-triage` — 读 `batch_qa_report.json` + `pipeline.log`，分类修复或请求用户授权 `--allow-failures`。

### Phase 4 — Translation（可选，按需）

仅在 Phase 2/3 出现大量 `translate_missing` 时启用：

```bash
# 配置 LANGCRAFT_CMD 或 OPENAI_API_KEY 后
python3 scripts/anthropic_content_pipeline.py \
  --batch-size 5 \
  --output-root artifacts/anthropic-content \
  --translate-mode auto \
  --resume-output
```

## 可选支线：Feishu 分发

**前置**：主线路径 Phase 2+ 已 PASS；用户明确要求 sync 验收。

```mermaid
flowchart LR
  QA[technical + content PASS] --> D1[D1 dry-run]
  D1 --> H[human review folder_path]
  H --> D2[D2 execute]
```

| Phase | 动作 | 门禁 |
|:-----:|------|------|
| D1 | `--sync-feishu`（无 execute） | `folder_path` 正确；人工审阅 `feishu_sync_commands.sh` |
| D2 | `--execute-feishu --resume-output` | `feishu_sync_report.json` PASS |

```bash
export FEISHU_DOC_ROOT_MODE=agent-docs-folder
export FEISHU_DOC_FOLDER_TOKEN='<agent-docs folder token>'

npm run anthropic:sync-dryrun
# 人工确认后
npm run anthropic:sync
```

**分发 PASS 不替代技术 PASS 或内容 PASS。**

## Stage 1 完成声明

仅在以下条件**全部**满足时，可声明 Stage 1 mainline 完成：

1. `pipeline_summary.json` → `overall_status: PASS`
2. 目标 batch 的 `batch_qa_report.json` → `qa_status: PASS`
3. 至少 1 篇抽样通过 content-quality-gate（结构、术语、来源）
4. 证据已写入 report/log，非 Agent 主观判断

Feishu D1/D2 **不是** Stage 1 完成的必要条件。

## 停止与升级

| 情况 | 动作 |
|------|------|
| QA FAIL | qa-triage → 修复 → 重跑；不 `--force-sync` |
| 源站结构变化 | 更新 ingest 逻辑；记录 `EXPERIENCE.md` |
| 需新厂商 | Stage 2 vendor-onboarding；不在 Stage 1 强行扩展 |
| 需商品化 | 转入 Stage 3 规划；不跳过 source library |

## 相关 Skills（active）

| Skill | 路径 | 职责 |
|-------|------|------|
| `source-discovery` | `skills/source-discovery/SKILL.md` | 审阅 discover 范围与 vendor 来源 |
| `content-quality-gate` | `skills/content-quality-gate/SKILL.md` | 内容 PASS 人工/模型辅助审校 |
| `qa-triage` | `skills/qa-triage/SKILL.md` | QA 失败分类与修复路径 |
| `vendor-onboarding` | Stage 2 规划 | 新厂商接入 |

## 参考

- `ARCHITECTURE.md` — 模块边界与质量门禁
- `DEBUG.md` — 排障与 E2E 清单
- `docs/superpowers/specs/2026-05-22-agent-docs-platform-design.md` — 设计规格
