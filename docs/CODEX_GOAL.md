# Codex `/goal` 提示词 — agent-docs 任务入口

本文件是 Codex `/goal` 从本仓库领取任务的入口提示词，不是架构文档。架构、阶段路线、目录结构、模块边界、代码重构方向以仓库根目录 `ARCHITECTURE.md` 为准。

将下方 XML **原样**作为 Codex `/goal` 的任务正文。执行前确保 Codex 在仓库根目录 `agent-docs/`。仅当本次任务进入 Feishu execute 支线时，才要求本机已 `lark-cli auth login`（user 身份）。

---

## 双专家交叉评审与验收（2026-05-22）

**专家 A（可靠性/架构）× 专家 B（质量/可观测性）** 对用户五项要求及既有共识进行交叉评审：

| 要求 | 评审结论 | 验收 |
|------|----------|:----:|
| 1. 中文优先抓取 | 代码已有 `pick_preferred_source_url`（`/zh-CN/` → `/zh/` HEAD 探测）；无中文且 `--translate` 开启才翻译。Goal 须写清顺序与 Gate | **PASS**（文档化） |
| 2. 图片抓取至关重要 | QA 已阻断 `image_download_failed` / `image_not_localized`；sync 后 `verification.image_count`。Goal 须列为硬门禁 | **PASS**（文档化） |
| 3. 日志 WARN/ERROR/进度/可重放 | `PipelineLogger` 写入 `{output_root}/pipeline.log`（JSON Lines）；各 stage 含 batch_id、source_url、error_code；与 `batch_qa_report.json` 等产物互补 | **PASS** |
| 4. 分批分步、低耦合 | discover / crawl / QA 主线路径；Feishu dry-run/execute 为可选支线。Goal 写入 Mainline 0–4 + Distribution D0–D2 | **PASS**（文档化） |
| 5. QA 流程 | `run_qa` + QA PASS 才 sync（默认）。Goal 与 DEBUG 对齐 | **PASS** |

**交叉验收结论**：共识已合并进下方 XML。`PipelineLogger` 已实现基础结构化日志（`pipeline.log`）；`<observability_contract>` 中 retry_count 等字段仍可迭代。**来源 URL 归因**：文档级 callout（Phase 1）与目录级 `📋 目录总纲`（Phase 2）均已实现。

---

## 入口执行原则（2026-05-22 更新）

当前 `/goal` 只负责把 Codex 带入正确任务边界。**第一阶段不是商品化交付，也不是 Feishu 同步优先；第一阶段主线是开发资料的高质量收集与完善**。

| 阶段 | 主目标 | 范围 |
|------|--------|------|
| Stage 1 — Source Library Foundation | 高质量收集、归档、完善开发资料源材料；完成技术 PASS 与内容 PASS | Anthropic active；OpenAI/Gemini/Cursor 仅保留架构接口；Feishu sync 为可选支线 |
| Stage 2 — Learning Library Architecture | 规划跨厂商主题 taxonomy、学习路径、深度分析模板 | 架构级设计，可产出草案，不作为 Stage 1 完成条件 |
| Stage 3 — Productization | 商品化包装、版权策略、SKU、更新承诺、发布前商业策略 | TODO，发布前专项处理 |

Stage 1 的成功标准：

- **技术 PASS**：来源发现、抓取、图片、结构、日志、可重跑、产物完整性、来源归因均可验证。
- **内容 PASS**：原文/中文优先材料完整、结构保真、术语一致、图片/表格/代码块未丢失、元数据与来源可追溯。
- **Feishu sync**：资料收集完善后的分发支线。只有技术 PASS + 内容 PASS 后才进入 dry-run/execute；不作为 Stage 1 主线阻断项，除非用户明确要求同步验收。
- **架构依据**：若本文件与 `ARCHITECTURE.md` 冲突，以 `ARCHITECTURE.md` 为准，并先更新本文件的入口约束。

## Goal Prompt

```xml
<task>
You are working in the git repository `agent-docs` at the workspace root.

Build and harden **Stage 1 of a multi-vendor AI/Agent technical documentation library** (Anthropic active; OpenAI/Gemini/Cursor reserved).

Stage 1 primary mission: high-quality collection and improvement of developer documentation source materials. Preserve authoritative source content first; do not skip ahead to deep analysis, course packaging, or commercial productization.

Deliver a production-grade source-library pipeline: source discovery, Chinese-first capture, image fidelity, structure preservation, source attribution, structured observability, replayable artifacts, decoupled phased rollout, and strict technical/content QA.

Feishu sync is an optional distribution branch after source collection is technically and editorially acceptable. Do not treat Feishu execute as the primary Stage 1 success criterion unless the user explicitly asks for sync validation.

Required Feishu layout (default mode `agent-docs-folder`):

FEISHU_DOC_FOLDER_TOKEN must point to a Drive folder literally named `agent-docs`.
Full path from Drive root (use `folder_path` in reports — NOT `folder_segments` alone):

agent-docs/                          ← FEISHU_DOC_FOLDER_TOKEN (folder name: agent-docs)
  anthropic-docs/
    Anthropic/
      Developer-docs/
        agents-and-tools/
          agent-skills/
            技能编写最佳实践          ← doc title: match source or faithful zh translation; NO "-import" suffix

飞书云文档的结构设计考虑：
  预期目录应当与资料来源网站保持一致（可基于 URL 来获得），Anthropic 官方大致目录：
  Anthropic/
    Anthropic Academy/   ← https://www.anthropic.com/learn
    Claude/
      Blog/             ← https://claude.com/blog
    Engineering/        ← https://www.anthropic.com/engineering
    Developer-docs/     ← https://platform.claude.com/docs/en/home
    Tutorials/          ← https://claude.com/resources/tutorials
    User Cases/         ← https://claude.com/resources/use-cases
    Courses/            ← https://claude.com/resources/courses（本阶段跳过，视频为主）

  注：Courses 主要是视频形式，本阶段不纳入。正文中的视频保留原始 URL，不下载、不嵌入。

  多厂商同级预留（本阶段仅实现 anthropic-docs）：
  agent-docs/
    anthropic-docs/
    openai-docs/
    gemini-docs/
    cursor-docs/

Do NOT use ad-hoc test roots like `agent-docs-e2e-real` as the permanent layout name.
If `FEISHU_DOC_ROOT_MODE=parent`, the token is the parent of `agent-docs` and the pipeline creates `agent-docs/` first.

Read first (in order): AGENTS.md, ARCHITECTURE.md, workflows/stage1_source_library.md, EXPERIENCE.md, DEBUG.md, scripts/anthropic_content_pipeline.py.
Treat ARCHITECTURE.md as the source of truth for architecture, directory structure, module boundaries, and the Agent Skills + Workflow control-plane design.
Follow workflows/stage1_source_library.md for Stage 1 mainline vs optional Feishu distribution branch.
</task>

<chinese_first_policy>
Priority order for every non-news URL (platform/code docs):

1. If URL already contains `/zh-CN/` or `/zh/` → fetch as-is.
2. Else if URL contains `/en/` → probe `/zh-CN/` variant via HEAD (then `/zh/`); use Chinese URL when available (`pick_preferred_source_url`).
3. If Chinese page returns not-found → fall back to original URL.
4. Translation (`LANGCRAFT_CMD` or OpenAI) ONLY when:
   - final content is not Chinese (`has_chinese` / `chinese_ratio`),
   - AND no Chinese source was available,
   - AND `--translate` / `--translate-mode` is enabled (not `off`).

News (`anthropic_news`) may remain English-only; do not force translation unless configured.

Preserve terms: Agent, Skill, Token, MCP, CLI, API, OAuth, JSON, Markdown, YAML, SDK.

QA blocks sync when `translate_missing` or `zh_output_language_check_failed`.
</chinese_first_policy>

<image_quality_contract>
Images are a **primary quality metric**, not optional decoration.

Pipeline behavior (preserve/enhance):
- Extract all markdown images → download to `{item_dir}/media/` → rewrite links to local `media/` paths.
- `DEFAULT_IMAGE_FETCH_TIMEOUT=180` for large platform.claude.com assets.
- Write `images.json` per item with per-image: source URL, status, file path, error if any.

QA MUST FAIL (block sync) on:
- `image_download_failed`
- `image_file_missing`
- `image_not_localized`
- `image_count_decrease` (output fewer images than source)

Feishu sync:
- Strip local `media/` refs from import markdown; insert via `docs +media-insert` with caption after `drive +import`.
- Post-sync: `verification.image_count >= expected_images` when source had images.

Retry policy for implementers: failed images should be retryable from `images.json` + logs without re-crawling entire batch.
</image_quality_contract>

<source_attribution>
飞书 `drive +import` 会剥离 YAML frontmatter，因此 **必须在 import payload 正文顶部** 写入可见的来源标注块（`build_feishu_source_attribution_block`），由 `prepare_feishu_import_markdown` 从 `final.*.md` frontmatter 生成。

**Phase 1（已实现）— 文档级标注**：
- 每篇同步文档顶部 blockquote callout，含：
  - `原文链接`
  - `发布时间`
- 产物：`{batch_dir}/sync_payload/{slug}.feishu.md` 含 callout；飞书正文可读可点击

**Phase 2（已实现）— 目录级索引**：
- 每个飞书文件夹生成/更新一篇 **`📋 目录总纲`** 云文档（`FEISHU_INDEX_DOC_TITLE`；勿用 `README.md`）
- 内容：该文件夹下已同步文档的表格（标题 | 原文链接 | 发布时间 | 飞书文档 | 状态）
- 幂等：`.feishu_index_cache.json` 按 `folder_token` 缓存 index doc_id；re-sync 优先 `docs +update --mode overwrite`，失败则 `drive +import` 并更新 cache
- 机器可读层：`{output_root}/feishu_folder_index.json` 聚合 `folder_path → items[]`；batch 内 `sync_payload/index_{suffix}.md`

**不推荐**：
- 仅依赖 per-folder `README.md` 文件名（飞书非 git；用户困惑；与正文 doc 难区分）
- 仅 frontmatter 不归因（import 后不可见）

验收：dry-run 检查 `sync_payload/*.feishu.md` 首段含 `资料来源` 与可点击 URL；`sync_payload/index_*.md` 与 `{output_root}/feishu_folder_index.json` 存在；execute 后 `docs +fetch` spot-check callout 与目录总纲表格。
</source_attribution>

<observability_contract>
Target standard: **from WARN/ERROR logs and progress stats alone, an operator can fully identify and retry every failed crawl or upload** without guessing.

Required log semantics (implement if missing):
- Levels: INFO (progress), WARN (recoverable/degraded), ERROR (item/batch failure).
- Progress: batch_id, item index/total, stage (`discover|crawl|translate|qa|sync_dryrun|sync_execute`), source_url.
- Failure record fields (JSON line or structured stderr):
  - url, stage, error_code, message, retry_count, artifact_path, batch_id, timestamp_utc

Existing artifacts that MUST remain populated (bridge until full logging):
- `batch_qa_report.json` → errors[] with codes like `image_download_failed: {url}`
- `images.json` → per-image status
- `feishu_sync_report.json` → items[].status, media_failures, verification
- `pipeline_summary.json` → overall_status, failed_batches

Codex/implementer: if adding logging, write `{output_root}/pipeline.log` append-only; do not log secrets.
</observability_contract>

<phased_delivery>
Design principle: **decouple stages, minimize blast radius, no skip-ahead**.

Follow `workflows/stage1_source_library.md` for the control-plane workflow. Stage 1 completion = mainline PASS (technical + content QA), NOT Feishu execute.

**Mainline (Stage 1 — required)**

| Phase | Action | Gate (must pass before next) | Coupling |
|-------|--------|------------------------------|----------|
| 0 | `--discover-only` | discover.json sane | none |
| 1 | smoke crawl: `--max-items 5 --no-qa --translate-mode off` | pipeline_summary PASS | crawl only |
| 2 | single item: `--max-items 1 --batch-size 1` + QA | batch_qa_report PASS (technical + content) | crawl+QA |
| 3 | small batch crawl: `--batch-size 5` + QA | QA PASS per batch | isolated batch dir |
| 4 | enable translation when needed: `--translate-mode auto` + LANGCRAFT/OpenAI | QA PASS; watch translate API limits | last mainline — highest cost/risk |

**Optional distribution branch (only when user explicitly requests Feishu sync validation)**

| Phase | Action | Gate | Coupling |
|-------|--------|------|----------|
| D0 | `--self-test-feishu-paths` | path unit tests OK | pre-sync only |
| D1 | sync dry-run: `--sync-feishu` (NO `--execute-feishu`) | folder_path matches URL map; review feishu_sync_commands.sh | requires mainline QA PASS |
| D2 | single/batch execute: `--execute-feishu --resume-output` | feishu_sync_report PASS; UI spot-check | sync only |

Rules:
- Do NOT treat D1/D2 as Stage 1 done unless user asked for sync validation.
- NEVER `--execute-feishu` before dry-run review for a new folder mapping.
- NEVER `--force-sync` / `--force-commit` without explicit user authorization.
- New output root OR delete `.feishu_folder_cache.json` after changing `feishu_folder_segments`.
- `--resume-output` only when intentionally continuing same output_root.

Default batch-size: 5–10 for first production run; 20 only after stable mainline QA (+ optional sync).
</phased_delivery>

<qa_gates>
QA is the **merge gate** between crawl and Feishu.

`batch_qa_report.json`:
- `qa_status`: PASS | FAIL | SKIPPED (`--no-qa` only for smoke)
- `errors[]`: machine-parseable `code: source_url` entries

Hard FAIL conditions (non-exhaustive — see `run_qa`):
- not_fetched, empty_or_too_short_output, not_found_output
- image_download_failed, image_file_missing, image_not_localized, image_count_decrease
- table/heading/link_count_decrease
- translate_missing, zh_output_language_check_failed

Sync gate: `sync_to_feishu` with `--execute-feishu` requires QA PASS unless `--force-sync`.
Post-sync gate: `feishu_sync_report.status` must be PASS (not PARTIAL); `verification.content_length >= 200`.
</qa_gates>

<rate_limits_and_performance>
Sequential processing is intentional (reduces WAF/API blast). Bottlenecks:
- Anthropic HTTP fetch: 3 retries, short sleep; no dedicated 429 backoff yet — use smaller batches + pause between batches if throttled.
- Translation (OpenAI/LangCraft): enable only in mainline Phase 4 when needed; serial calls.
- Feishu lark-cli: highest risk at execute — each doc = import + N media-insert + fetch verify. Mitigate: batch-size 5–10, dry-run first, retry failed items from report.

Do NOT add concurrency until observability + retry story is complete.
</rate_limits_and_performance>

<directory_validation_playbook>
Confirm mapping:
1. `python3 scripts/anthropic_content_pipeline.py --self-test-feishu-paths`
2. `--sync-feishu` dry-run → check `folder_path` (full, with `agent-docs/`) and `folder_segments` (relative to token)
3. Execute → `feishu_sync_report.json` + UI walk: agent-docs → anthropic-docs → Anthropic → …

Correct misplaced docs:
- Wrong mapping code → fix `feishu_folder_segments` / `VENDOR_LIBRARIES` → new output-root or clear `.feishu_folder_cache.json`
- Wrong token → set `FEISHU_DOC_FOLDER_TOKEN` to folder named `agent-docs`
- Wrong Feishu folders → manual delete/move in Drive; pipeline does not auto-migrate

Canonical acceptance path (best-practices example):
`agent-docs/anthropic-docs/Anthropic/Developer-docs/agents-and-tools/agent-skills`
</directory_validation_playbook>

<known_constraints>
Preserve unless fixing a verified bug:
- Feishu sync: `drive +import`, NOT `docs +create --content` (v2 empty docs).
- Import markdown: strip YAML frontmatter and local `media/` refs; images via `docs +media-insert`.
- Folder cache: `{output_root}/.feishu_folder_cache.json` keyed `parent_token::name`.
- `parse_lark_cli_json`: JSONDecoder.raw_decode (stderr after JSON).
- lark-cli subprocess: plain relative paths, NOT `@file`.
- Skip `claude.com/resources/courses` URLs.
</known_constraints>

<structured_output_contract>
Return at the end:
1. Summary of code/doc changes (bullet list)
2. Mainline phase table (0–4: PASS/SKIP/BLOCKED + evidence)
3. Optional distribution table (D0–D2: PASS/SKIP/BLOCKED + evidence) — only if user requested sync
4. E2E commands run and exit codes
5. QA summary: qa_status, error counts by code
6. Observability gap report: what logging exists vs observability_contract
7. Explicit PASS/FAIL against Stage 1 mainline (technical + content QA)
8. If sync ran: feishu_sync_report.json folder_path, doc_url, verification, media_failures
9. Residual risks
</structured_output_contract>

<default_follow_through_policy>
Default to the most reasonable low-risk interpretation and keep going.
Do not ask routine questions.

Bootstrap only (Phase 0): if FEISHU_DOC_FOLDER_TOKEN unset, create `agent-docs` via `lark-cli drive +create-folder --name agent-docs`, export token.
Production: token MUST be pre-provisioned folder named `agent-docs` — do not auto-create without user context.

If auth shows `needs_refresh`, run proxyless re-auth before sync.
</default_follow_through_policy>

<completeness_contract>
Do not stop at analysis. You must:
1. Fix bugs blocking source capture, QA, images, or false-positive PASS.
2. Implement or document gaps for observability_contract (prefer minimal structured logging if time permits).
3. Update EXPERIENCE.md with dated entries.
4. Update DEBUG.md E2E checklist if gaps exist.
5. Run verification_loop mainline through at least Phase 3 before claiming Stage 1 done.
6. Run distribution branch (D1/D2) only when user explicitly requests Feishu sync validation — not required for Stage 1 completion.
</completeness_contract>

<verification_loop>
See `workflows/stage1_source_library.md` for the full control-plane workflow.

**Mainline minimum (Stage 1 done — adjust output-root if needed):**

```bash
python3 -m py_compile scripts/anthropic_content_pipeline.py
npm run anthropic:discover
npm run anthropic:crawl:smoke

python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/e2e-goal-verify \
  --no-include-code-docs --no-include-news \
  --translate-mode off

python3 scripts/anthropic_content_pipeline.py \
  --batch-size 5 \
  --output-root artifacts/e2e-goal-verify \
  --no-include-code-docs --no-include-news \
  --translate-mode off \
  --resume-output
```

Mainline acceptance (required for Stage 1 completion):
- pipeline_summary.json: overall_status == PASS
- batch_qa_report.json: qa_status == PASS (technical + content)
- source/final files, images.json, pipeline.log present and consistent
- spot-check: source attribution, structure fidelity, terminology preservation

**Optional distribution branch (only when user explicitly requests Feishu sync validation):**

```bash
npm run feishu:check:full
python3 scripts/anthropic_content_pipeline.py --self-test-feishu-paths

export FEISHU_DOC_ROOT_MODE=agent-docs-folder
# FEISHU_DOC_FOLDER_TOKEN → folder named agent-docs

python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/e2e-goal-verify \
  --no-include-code-docs --no-include-news \
  --translate-mode off \
  --sync-feishu \
  --resume-output

# Human review feishu_sync_commands.sh + folder_path, then:

python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/e2e-goal-verify \
  --no-include-code-docs --no-include-news \
  --translate-mode off \
  --sync-feishu --execute-feishu \
  --resume-output
```

Distribution acceptance (required only if sync branch ran):
- feishu_sync_report.json: status == PASS (not PARTIAL)
- folder_path == agent-docs/anthropic-docs/Anthropic/Developer-docs/agents-and-tools/agent-skills
- doc title has no "-import" suffix
- verification.content_length >= 200
- verification.image_count >= expected_images (when images present)

If any check fails, fix and re-run until PASS or document blocker with evidence.
</verification_loop>

<action_safety>
Minimal diffs only. No unrelated refactors. Do not commit secrets. Do not git commit unless explicitly needed.
</action_safety>

<grounding_rules>
Ground every claim in command output, JSON reports, or file diffs.
Label hypotheses clearly. Do not claim E2E PASS without running commands.
</grounding_rules>
```

---

## 使用说明

1. 先读 `ARCHITECTURE.md` 与 `workflows/stage1_source_library.md`。
2. 将上方 XML 粘贴到 Codex `/goal` 执行。
3. **主线路径**：按 Phase 0→4 推进（discover → smoke → single QA → batch QA → translate 按需）。
4. **Stage 1 完成标准**：技术 PASS + 内容 PASS（见 `batch_qa_report.json`）；**不要求** Feishu execute。
5. **分发支线**（可选）：仅当用户明确要求 sync 验收时，在 mainline PASS 后执行 D0→D1→D2；需 `FEISHU_DOC_FOLDER_TOKEN` 与 user 登录。
6. 验收：mainline 看 QA report + 抽样内容；sync 支线看 `folder_path` + UI 逐级展开 + 图片与中文正文 spot-check。

## 字段契约

| 字段 | 含义 |
|------|------|
| `folder_segments` | 相对 `FEISHU_DOC_FOLDER_TOKEN` 的路径段（lark-cli 建目录用） |
| `folder_path` | 从云盘根起的完整路径（E2E 与 UI 验收用，含 `agent-docs/`） |

## 与 `parent` 模式的区别

| 模式 | `FEISHU_DOC_FOLDER_TOKEN` 指向 | 飞书完整路径前缀 |
|------|--------------------------------|------------------|
| `agent-docs-folder`（默认） | 已存在的 `agent-docs/` 文件夹 | `agent-docs/anthropic-docs/Anthropic/…` |
| `parent` | `agent-docs` 的父目录（如云盘根） | 同上（流水线自动创建 `agent-docs/`） |

## 已知代码缺口（后续迭代）

| 缺口 | Goal 章节 | 现状 |
|------|-----------|------|
| 结构化 pipeline 日志（retry_count 等待补字段） | `<observability_contract>` | `{output_root}/pipeline.log`（JSON Lines，基础字段已实现） |
| 飞书目录级来源索引（`📋 目录总纲` doc） | `<source_attribution>` Phase 2 | 已实现：`sync_feishu_folder_indexes` + `feishu_folder_index.json` |
| HTTP 429 专用退避 | `<rate_limits_and_performance>` | 仅 3 次通用重试 |
| 飞书 API 限流重试 | 同上 | `run_lark_cli` 失败即记录，无 backoff |
