---
name: source-discovery
description: >-
  Reviews Anthropic (and future vendor) source URL discovery output for Stage 1
  source library collection. Use after `npm run anthropic:discover`, when
  validating discover.json scope, excluding courses/video-only paths, or before
  starting a batch crawl.
---

# Source Discovery

Stage 1 控制平面 skill：审阅 **发现阶段** 的 URL 范围，不执行抓取。

## 何时使用

- Phase 0 完成后（`workflows/stage1_source_library.md`）
- 用户问「discover 范围对不对」「要不要加/减来源」
- 新 batch crawl 前做范围 sanity check

## 确定性工具（你来调用）

```bash
npm run anthropic:discover
# 产物：artifacts/anthropic-discovery/discover.json
```

等价：

```bash
python3 -m agent_docs.cli --discover-only --output-root artifacts/anthropic-discovery
```

（若 `python3 -m agent_docs.cli` 不可用，fallback 到 `python3 scripts/anthropic_content_pipeline.py --discover-only`。）

## 审阅清单

1. **来源覆盖**
   - `platform.claude.com` 开发者文档（llms.txt）
   - `code.claude.com/docs` Claude Code 文档
   - `anthropic.com` sitemap 下允许前缀：`news`, `research`, `engineering`, `learn`, `economic-futures`, `system-cards`
   - `claude.com` blog / tutorials / use-cases（非 courses）

2. **必须排除（Stage 1）**
   - `/resources/courses`（视频为主，见 `FEISHU_EXCLUDED_URL_PATHS` / `ARCHITECTURE.md`）
   - 明显非文档页（登录、404 模板、纯营销落地页）

3. **数量与重复**
   - `discover.json` 的 `count` 与预期量级一致（全量通常数百～数千）
   - 无大量重复 `source_url`（normalize 后应唯一）

4. **厂商注册表**
   - 当前 active：`anthropic`（`agent_docs/vendors/registry.py`）
   - `openai` / `gemini` / `cursor` 为 reserved，不在 Stage 1 强行扩展

## 输出格式

```markdown
## Source Discovery Review

- **Verdict**: APPROVE | REVISE | BLOCK
- **discover.json**: `<path>` (count=N)
- **Coverage**: platform / code / news / claude.com resources — 简要
- **Excluded**: 列出应跳过的 URL 模式
- **Risks**: 结构变化、缺失分区、需用户确认的 scope 变更
- **Next command**: 建议的 smoke 或 single-item 命令
```

## 边界

- **不做**：抓取、翻译、QA、Feishu sync
- **不替代**：`content-quality-gate`（内容审校）或 `qa-triage`（QA 失败排障）
- 发现 ingest 逻辑 bug 时，记录到 `EXPERIENCE.md` 并改 `agent_docs/ingest/`，而非在 discover 阶段手工改 URL 清单糊弄过去

## 参考

- `workflows/stage1_source_library.md` Phase 0
- `ARCHITECTURE.md` — 输入源与 vendor registry
- `DEBUG.md` — discover 相关排障
