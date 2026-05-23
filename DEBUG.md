# DEBUG.md

Agent 排障手册。按症状查找；修复后把可复用结论写入 `EXPERIENCE.md`。

## 验证清单（改代码后）

```bash
# 1) 飞书接入文件完整性（CI 同款）
npm run feishu:check

# 2) Python 语法
python3 -m py_compile scripts/anthropic_content_pipeline.py

# 3) 流水线 smoke（网络依赖，5 条、无 QA/翻译）
npm run anthropic:crawl:smoke
```

飞书接入验证（推荐顺序）：

```bash
npm run feishu:check          # 文件 + CLI 可用
npm run feishu:check:auth     # auth_level=bot|user
lark-cli auth list            # 应有 logged-in user（文档同步前）
npm run feishu:doctor         # 网络/配置/token；ok:false 时看 checks[]
```

可选（需 `auth_level=user` + 流水线产物）：

```bash
npm run anthropic:sync-dryrun
```

**auth_level 说明**：见 `docs/FEISHU_CLI_INTEGRATION.md` §4.1。`check:auth` 在仅 bot 时也会 `[OK]`，但文档同步仍需 user 登录。

## E2E 验收清单（飞书 sync）

**前置**：`FEISHU_DOC_FOLDER_TOKEN` 指向名为 **`agent-docs`** 的文件夹；`FEISHU_DOC_ROOT_MODE=agent-docs-folder`（默认）。**Stage 1 主线须先 QA PASS**；Feishu sync 为可选支线（见 `workflows/stage1_source_library.md`）。

```bash
export FEISHU_DOC_ROOT_MODE=agent-docs-folder
export FEISHU_DOC_FOLDER_TOKEN='<agent-docs 文件夹 token>'

# 1) 抓取 1 篇 + QA
python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/e2e-verify \
  --no-include-code-docs --no-include-news --translate-mode off

# 2) sync execute（需 --resume-output 若 output 已有 batch）
python3 scripts/anthropic_content_pipeline.py \
  --max-items 1 --batch-size 1 \
  --output-root artifacts/e2e-verify \
  --no-include-code-docs --no-include-news --translate-mode off \
  --sync-feishu --execute-feishu --resume-output
```

**机器验收**（读 `artifacts/e2e-verify/batch-001/`）：

| 检查项 | 期望 |
|--------|------|
| `batch_qa_report.json` → `qa_status` | `PASS` |
| `feishu_sync_report.json` → `status` | `PASS`（非 `PARTIAL`） |
| `folder_path` | `agent-docs/anthropic-docs/Anthropic/Developer-docs/agents-and-tools/agent-skills` |
| `doc_url` | 可打开，标题无 `-import` |
| `verification.content_length` | ≥ 200 |
| `verification.image_count` | ≥ `expected_images`（有图时） |

**UI 验收**：在飞书逐级展开：

```text
agent-docs/ → anthropic-docs/ → Anthropic/ → Developer-docs/ → agents-and-tools/ → agent-skills/ → {文档}
```

Codex 一次性任务提示词：[`docs/CODEX_GOAL.md`](./docs/CODEX_GOAL.md)

**日志**：结构化日志见 `{output_root}/pipeline.log`（JSON Lines）；ERROR 行含 `error_code` 与 `artifact_path`。

---

## 飞书 CLI

### 症状：`No permission to access`

**原因**：OAuth/应用授权未完成，**不等于**个人账号不支持。常见为代理、过期会话、未完成浏览器授权、企业应用审批。

**步骤**：

```bash
lark-cli auth logout
npm run feishu:auth:device:proxyless
# 用户在浏览器完成授权
npm run feishu:check:full
lark-cli auth list
```

详见 `docs/FEISHU_CLI_INTEGRATION.md` §4.2。

### 症状：鉴权超时 / 代理相关失败

**原因**：`ALL_PROXY` / `HTTP(S)_PROXY` 干扰 OAuth。

**步骤**：

```bash
npm run feishu:auth:device:proxyless
# 或
LARK_CLI_NO_PROXY=1 npm run feishu:auth
```

### 症状：`lark-cli` 未找到

```bash
npm run feishu:install
npm run feishu:check
```

### 症状：授权状态不明

```bash
npm run feishu:status
lark-cli auth list
npm run feishu:doctor
```

### 症状：CI 通过但本地 auth 失败

CI 只跑 `feishu:check`，**不要求登录**。本地需单独 `feishu:check:auth`。

---

## Anthropic 流水线

### 症状：立即 FAIL，`output_root already contains batch directories`

**原因**：防旧 batch 混入的保护。

**处理**：

- 新跑：换 `--output-root` 或清空旧 `batch-*`
- 续跑：显式 `--resume-output`

```bash
python3 scripts/anthropic_content_pipeline.py --resume-output --output-root artifacts/anthropic-content
```

### 症状：`overall_status: FAIL`，`failed_batches` 非空

**步骤**：

1. 打开 `artifacts/anthropic-content/pipeline_summary.json`
2. 对每个失败 batch 读 `batch-XXX/batch_qa_report.json`
3. 按 `errors[]` 条目对照下表

### QA 错误码对照

| errors 条目 | 含义 | 常见修复 |
|-------------|------|----------|
| `missing_files` | 预期 md/json 不存在 | 重跑该 batch；查网络/权限 |
| `empty_output` | 正文有效长度过短 | 源站结构变化；查 `raw.html` / `source.md` |
| `table_count_decrease` | 输出表格少于源 | 抓取/翻译丢表格；查 markdown 转换 |
| `heading_count_decrease` | 标题减少 | 同上 |
| `link_count_decrease` | 链接减少 | 翻译或清理逻辑过 aggressive |
| `image_download_failed` | 图片 HTTP 失败 | 网络、防盗链、URL 失效 |
| `image_file_missing` | images.json 有记录但文件不存在 | 磁盘/路径问题 |
| `image_not_localized` | 正文未引用 `media/` | `process_target` 替换逻辑 |
| `translate_missing` | 需要翻译但未产出中文 | 配置翻译器 |
| `zh_output_language_check_failed` | final.zh 中文占比不足 | 翻译质量或源已是英文壳 |

### 症状：翻译相关 QA 全失败

**检查**：

```bash
echo "$LANGCRAFT_CMD"
echo "${OPENAI_API_KEY:+set}"
```

- 设 `LANGCRAFT_CMD` 或 `OPENAI_API_KEY`
- smoke 可先 `--translate-mode off`（`anthropic:crawl:smoke` 已默认 off）
- 全量需翻译：确认 `translate_mode` 非 off

### 症状：discover 条数异常

```bash
npm run anthropic:discover
cat artifacts/anthropic-discovery/discover.json | python3 -m json.tool | head
```

检查 `--no-include-platform-docs` / `--no-include-news` 等是否误传。

### 症状：单 URL 反复失败

1. 在 `discover.json` 或 manifest 找到 `source_url`
2. 打开对应 `{batch}/{idx}_{slug}/source.md` 与 `raw.html`
3. 手动 `curl` 对比源站是否可访问
4. 若是源站限流，稍后重试或减小 `--batch-size`

---

## 飞书同步

### 症状：`status: BLOCKED`, `qa_status=FAIL`

**预期行为**。先修 QA 或用户明确授权 `--force-sync`。

### 症状：`FEISHU_DOC_FOLDER_TOKEN missing`

```bash
export FEISHU_DOC_FOLDER_TOKEN='...'
npm run anthropic:sync-dryrun   # 先 dry-run
npm run anthropic:sync          # 再 execute
```

### 症状：`lark-cli not installed`

```bash
npm run feishu:install
npm run feishu:check:auth
```

### 症状：`PARTIAL` / 部分文档创建失败

1. 读 `batch_manifest.json` → `feishu.items`
2. 检查 `feishu_sync_commands.sh`，可手动重跑失败命令
3. 查 `lark-cli`  stderr（权限、folder token、内容格式）

### 症状：dry-run 成功但 execute 失败

dry-run 只生成命令，**不代表已上传**。execute 需要：

- 有效 `FEISHU_DOC_FOLDER_TOKEN`
- `lark-cli` 已登录
- 从 `output_root` 执行（脚本内 `cd` 已处理）

---

## Git 提交

### 症状：`git commit` 未发生

检查 `batch_qa_report.json`：

- `qa_status != PASS` 且未 `--force-commit` → `git_commit: false, reason: blocked_by_qa`
- 无变更 → git 返回非 0（`commit_batch` 返回 false）

### 症状：误提交大产物

- 确认 `.gitignore` 是否应忽略 `artifacts/`
- 本仓库 `--commit` 设计为提交 batch 内容；执行前需用户确认

---

## 日志与证据位置

| 文件 | 内容 |
|------|------|
| `pipeline_summary.json` | 全流水线汇总 |
| `batch_manifest.json` | 单批 items + QA + feishu + git |
| `batch_qa_report.json` | QA 错误列表 |
| `discover.json` | URL 清单 |
| `feishu_sync_commands.sh` | 可复现同步命令 |
| 终端 stdout | 流水线 JSON 摘要（`main` 打印） |

## 升级排障信息

- 可复现步骤 → 追加 `DEBUG.md` 对应章节
- 根因/决策 → 追加 `EXPERIENCE.md` 一条记录
