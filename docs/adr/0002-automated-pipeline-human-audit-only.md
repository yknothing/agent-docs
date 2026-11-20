# ADR-0002: 流水线全自动门禁，人工仅终验与抽样审计

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: 产品/架构讨论（用户确认意图）
- **Related**: [ADR-0001](./0001-source-library-and-pluggable-delivery.md), `workflows/stage1_source_library.md`, `skills/content-quality-gate/SKILL.md`, `skills/qa-triage/SKILL.md`

---

## Context

### 用户声明

> 不应当在中间环节有人工确认的环节，人工主要是做最终的验收和抽样审计。

### 当前仍存在的「中间人工卡点」

| 环节 | 现状 | 性质 |
|------|------|------|
| Feishu sync | dry-run → **用户确认** → `--execute-feishu` | 每批/每次同步的流程门禁 |
| `content-quality-gate` skill | 描述为「内容 PASS 的人工/模型辅助审校」 | 易被理解为阻塞 Stage 1 |
| `qa-triage` skill | 列出「Needs user approval: force-*」 | 合理，但文档未区分「常态 vs 例外」 |
| README / CODEX_GOAL | 「sync-dryrun → 用户确认 → sync execute」 | 默认工作流含人工闸门 |
| Feishu OAuth | 浏览器一次性授权 | **鉴权**，非 per-doc 确认（可保留） |

控制平面 spec（`2026-05-22-agent-docs-platform-design.md` §2.1）将「人工确认点」列在控制平面职责中——需 **收窄语义**：人工确认仅用于 **例外 override** 与 **终验抽样**，而非每条 happy path。

### 设计原则（已有，需强化执行）

- 完成声明必须基于 **artifact / report / test**（`ARCHITECTURE.md`）。
- Agent Skills 负责 **开放判断与例外**；Tools 负责 **确定性 PASS/FAIL**。
- 常态路径：**机器 QA 门禁** 即足够；人不做 batch 间 checkpoint。

---

## Decision

### 1. 常态流水线（无 blocking 人工步骤）

```text
discover → ingest → QA(technical + content) → library persist
                    ↓ PASS（batch_qa_report / pipeline_summary）
              optional: delivery adapter(s)（各自 machine verify）
                    ↓
              human: 最终验收 + 抽样审计（非 blocking）
```

### 2. 人工职责边界

| 允许 | 不允许（常态） |
|------|----------------|
| 最终验收：阅读 `pipeline_summary.json`，确认 Stage 1 可声明完成 | 每批 crawl 后等人点头继续 |
| 抽样审计：N 篇 `source.md` vs `final.*.md`、图片、链接 | dry-run 通过后等人批准 execute |
| 例外授权：`--force-sync`、`--allow-failures` 等（显式 flag + 记录） | 将 Agent skill 审校作为 merge 硬门禁 |
| 一次性 OAuth / 密钥配置 | 每篇文档导入前人工确认 |

### 3. dry-run  repositioning

- **保留** delivery dry-run 作为 **调试与契约测试** 模式（生成 report + commands，不上传）。
- **不再** 作为「execute 的前置人工审批步骤」。
- 目标默认（配置齐全且 QA PASS 时）：`--delivery=feishu --execute` 可 **自动执行**；dry-run 仅 via `--dry-run` 显式开启。

### 4. Skills 角色调整

| Skill | 调整后定位 |
|-------|------------|
| `content-quality-gate` | QA PASS **之后** 的抽样/深度审校；**不阻塞** pipeline |
| `qa-triage` | FAIL 时根因分类与修复建议；force-* 需用户授权 |
| `source-discovery` | discover 范围审阅（可 Agent 自动 + 报告，非人工 batch 闸） |

### 5. 文档统一改后验证链（机器）

改 ingest/QA 后 **仅跑工具链**，无人闸：

```text
lint:py → test:py → anthropic:crawl:smoke → anthropic:verify:qa
```

（已在 `workflows/stage1_source_library.md` 与 DEBUG 对齐方向；本 ADR 要求 **删除**「sync 前用户确认」作为默认路径描述。）

---

## Consequences

### Positive

- 流水线可无人值守跑完 Stage 1 主线（除 OAuth 首次配置）。
- Agent 与 CI 行为一致：都以 report PASS 为准。
- 人工精力集中在高价值审计，而非重复点击 approve。

### Negative

- 错误 folder mapping 或翻译质量可能在 execute 后才暴露 → 靠 **delivery adapter 自检**（正文长度、图片数、抽样 fetch）与 **可重放 report** 缓解。
- 需加强 `feishu_sync_report.json` / 未来 delivery report 的 **machine-verifiable** 字段，替代「人眼扫 dry-run」。

### Metrics / 验收

- 默认 npm 文档路径中 **不再出现**「用户确认后 execute」作为必步骤。
- Stage 1 workflow 完成声明 checklist **仅引用 JSON report PASS**，不引用「人工已确认」。

---

## Alternatives considered

| 方案 | 未采纳原因 |
|------|------------|
| 完全取消 dry-run | 丢失调试与 mapping 回归手段 |
| 保留 dry-run 人工闸作为默认 | 与用户「中间无人工确认」冲突 |
| 用 LLM 替代人工终验 | 用户明确要求人工做 **最终验收和抽样**；LLM 可作辅助，不作唯一 gate |
