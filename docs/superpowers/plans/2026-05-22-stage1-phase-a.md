# Stage 1 Source Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or implement inline with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地已批准的平台设计 Phase A——workflow 控制文档 + Codex goal 主/支线 Phase 对齐，使 Stage 1 以 source library + 技术/内容 PASS 为完成标准。

**Architecture:** Agent Skills + Workflow 控制平面；`workflows/stage1_source_library.md` 定义主线路径；Feishu 为 optional distribution branch；`docs/CODEX_GOAL.md` 仅作 Codex 入口并引用 `ARCHITECTURE.md`。

**Tech Stack:** Markdown workflows、现有 `anthropic_content_pipeline.py`、npm scripts、JSON QA reports

**Spec:** `docs/superpowers/specs/2026-05-22-agent-docs-platform-design.md`（Approved 2026-05-22）

---

## File Map

| 文件 | 动作 | 职责 |
|------|------|------|
| `workflows/stage1_source_library.md` | Create | Stage 1 控制流程 |
| `docs/CODEX_GOAL.md` | Modify | Phase 主/支线、verification_loop、completeness |
| `docs/superpowers/specs/2026-05-22-agent-docs-platform-design.md` | Modify | 状态 → Approved |
| `ARCHITECTURE.md` | Modify | 目录树标注 workflow 已落地 |
| `AGENTS.md` | Modify | 任务路由增加 workflow 引用 |

---

### Task 1: Workflow 控制文档

**Files:**
- Create: `workflows/stage1_source_library.md`

- [x] **Step 1:** 写入 Phase 0–4 主线路径、D1/D2 分发支线、PASS 条件、Skills 介入点
- [x] **Step 2:** 自检与 `ARCHITECTURE.md` 质量门禁一致

---

### Task 2: CODEX_GOAL Phase 对齐

**Files:**
- Modify: `docs/CODEX_GOAL.md` — `<phased_delivery>`, `<completeness_contract>`, `<verification_loop>`, `<structured_output_contract>`, 使用说明

- [x] **Step 1:** 将 `<phased_delivery>` 拆为 Mainline 0–4 + Optional Distribution D1–D2
- [x] **Step 2:** `completeness_contract` 改为至少 Phase 3 mainline PASS；Feishu 仅用户要求时
- [x] **Step 3:** `verification_loop` 拆 mainline 与 distribution 两段
- [x] **Step 4:** 更新使用说明 Phase 描述

**Mainline phased_delivery 目标内容：**

| Phase | Action | Gate |
|-------|--------|------|
| 0 | `--discover-only` | discover.json sane |
| 1 | smoke `--max-items 5 --no-qa` | pipeline_summary PASS |
| 2 | single item + QA | batch_qa_report PASS |
| 3 | batch `--batch-size 5` + QA | QA PASS per batch |
| 4 | `--translate-mode auto` when needed | QA PASS |

**Optional Distribution:**

| Phase | Action | Gate |
|-------|--------|------|
| D1 | `--sync-feishu` dry-run | folder_path + human review |
| D2 | `--execute-feishu` | feishu_sync_report PASS |

---

### Task 3: 文档交叉引用

**Files:**
- Modify: `docs/superpowers/specs/2026-05-22-agent-docs-platform-design.md`
- Modify: `ARCHITECTURE.md`
- Modify: `AGENTS.md`

- [x] **Step 1:** Spec 状态改为 Approved
- [x] **Step 2:** ARCHITECTURE 目录树标注 `workflows/stage1_source_library.md` 已存在
- [x] **Step 3:** AGENTS 任务路由增加「Stage 1 workflow」→ `workflows/stage1_source_library.md`

---

### Task 4: 验证

- [x] **Step 1:** 人工检查三文档 Phase 编号与 PASS 条件一致
- [x] **Step 2:** 无需跑 smoke（仅文档变更）

---

## 后续 Phase B–E（本 plan 范围外）

| Phase | 内容 |
|-------|------|
| B | 抽出 `agent_docs/core` + `vendors` |
| C | 抽出 `ingest` + `qa` |
| D | 抽出 `sinks/feishu` |
| E | 落地 `skills/*/SKILL.md` |

见 platform design spec §5.3。

---

## Self-Review

- Spec §3 Stage 1 数据流 → Task 1 workflow ✓
- Spec §4 质量门禁 → workflow PASS 条件 ✓
- Spec §5.3 Phase A → Task 2–3 ✓
- 无 TBD 占位符 ✓
