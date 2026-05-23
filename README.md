# agent-docs

多厂商 AI/Agent 技术资料库基础设施：以 **Agent Skills + Workflow** 为核心控制流程，以确定性 tools 承担抓取、格式处理、图片本地化、QA、CLI 封装、hooks 与自动化测试。

当前 Stage 1 聚焦开发资料源材料的高质量收集与完善；Feishu 同步是资料 PASS 后的可选分发支线，后续再规划跨厂商 taxonomy、学习路径、深度分析与商品化。

| 厂商库 | 飞书根 | 状态 |
|--------|--------|------|
| Anthropic | `anthropic-docs/` | **active**（`scripts/anthropic_content_pipeline.py`） |
| OpenAI | `openai-docs/` | reserved |
| Gemini | `gemini-docs/` | reserved |
| Cursor | `cursor-docs/` | reserved |

飞书云盘完整路径：`agent-docs/{vendor}-docs/{Vendor}/…`。`FEISHU_DOC_FOLDER_TOKEN` 必须指向名为 **`agent-docs`** 的文件夹（勿用 `agent-docs-e2e-real` 等临时名作生产根）。详见 [AGENTS.md](./AGENTS.md) 与 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## Agent 文档

面向 AI Agent 的仓库指南（建议优先阅读）：

| 文档 | 用途 |
|------|------|
| [AGENTS.md](./AGENTS.md) | Agent 入口：任务路由、约束、命令速查 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 系统结构、流水线、QA 与产物 |
| [DEBUG.md](./DEBUG.md) | 分场景排障与验证清单 |
| [EXPERIENCE.md](./EXPERIENCE.md) | 踩坑与决策记录（可追加） |

## 快速开始

```bash
# 安装飞书 CLI（官方推荐）
npm run feishu:install

# 初始化应用配置（生成配置向导）
npm run feishu:config

# 登录飞书（推荐权限范围）
npm run feishu:auth

# 查看登录状态
npm run feishu:status
```

## Anthropic 全量抓取流水线

仓库新增了 `scripts/anthropic_content_pipeline.py`，用于：

- 抓取 Anthropic 技术类官方内容：
  - `platform.claude.com` 文档
  - `code.claude.com/docs`（Claude Code）
  - Anthropic 官网技术博客/文章（来自 sitemap）
- 中文优先：先尝试 `/zh-CN/`，再尝试 `/zh/`，无中文时触发翻译；若未配置翻译器，QA 会阻断中文缺失
- 保留原始结构：markdown 表头、列表、链接、图片占位一并落地
- 图片本地化：下载图片到 `media/` 并在正文中引用本地路径
- 分批：按 `batch_size` 生成 `batch-xxx` 目录和 `batch_manifest.json`
- QA：校验抓取结果文件、正文非空、翻译语言、表格/标题/链接/图片计数与图片本地化
- 可选飞书同步：生成可执行命令并支持 dry-run；默认只有 QA PASS 才允许同步

### 重要环境变量

- `LANGCRAFT_CMD`：可选，若设置则用于命令行翻译；例如：
  - `export LANGCRAFT_CMD='node path/to/langcraft-cli --translate --from en --to zh --markdown'`
- `OPENAI_API_KEY`：未配置 `LANGCRAFT_CMD` 时，可走 OpenAI 翻译（默认）
- `FEISHU_DOC_FOLDER_TOKEN`：指向云盘文件夹 **`agent-docs`** 的 token（`--sync-feishu --execute-feishu` 时必须；dry-run 可生成占位命令）
- `FEISHU_DOC_ROOT_MODE`：默认 `agent-docs-folder`；token 为 `agent-docs` 父目录时设 `parent`

### 常用命令

```bash
# 1) 仅发现目标清单（用于核验范围）
npm run anthropic:discover

# 2) 小规模验证（5 条，跳过 QA，关闭翻译）
npm run anthropic:crawl:smoke

# 3) 全量抓取（默认分批；任一批 QA FAIL 时命令退出非 0）
npm run anthropic:crawl

# 4) 全量抓取并自动提交（QA 通过才提交；支持 --force-commit 覆盖）
npm run anthropic:commit

# 5) 飞书同步 dry-run（只生成命令稿；状态为 DRY_RUN，不代表已上传）
npm run anthropic:sync-dryrun

# 6) 飞书同步执行（依赖 lark-cli、token，且默认要求 QA PASS）
npm run anthropic:sync
```

### 多批次与 QA 政策

- 全量抓取默认会按 `batch_size` 进行分批。
- 默认不复用已有 `batch-*` 输出目录，避免旧产物混入；需要断点续跑时显式传 `--resume-output`。
- 每个 batch 会生成：
  - `batch_manifest.json`（本批元数据、QA、可选飞书同步结果）
  - `batch_qa_report.json`（QA 详情，提交阻断依据）
  - `feishu_sync_commands.sh`（可复现的同步命令文件；dry-run 生成，execute 才实际上传）
- 建议执行流：
  - 先跑 `anthropic:discover`（确认范围）
  - 再跑 `anthropic:crawl:smoke`（验证流程）
  - 再跑 `anthropic:crawl`
  - 检查 `batch_qa_report.json`，通过后再 `anthropic:commit`
  - 通过后再 `anthropic:sync-dryrun` / `anthropic:sync`
  - 只有明确接受风险时才使用 `--force-sync` 或 `--allow-failures`

### 产物结构

默认输出目录：`artifacts/anthropic-content`（可通过 `--output-root` 覆盖）

```bash
batch-001/
  001_xxx/                 # 单篇文档
    source.md               # 原始 markdown（含 metadata）
    final.zh.md / final.en.md # 最终产物
    images.json             # 图片下载与状态记录
    raw.html                # 非新闻来源的 html 原文
    media/                  # 图片资源
    feishu_sync_commands.sh # 本批同步脚本
  batch_manifest.json
  batch_qa_report.json
```

## 目录

- `AGENTS.md` / `ARCHITECTURE.md` / `DEBUG.md` / `EXPERIENCE.md`：Agent 工作文档
- `docs/FEISHU_CLI_INTEGRATION.md`：接入说明（含 AI Assistant 模式步骤）
- `scripts/`：用于安装与接入的脚本
  - `setup-feishu-cli.sh`
  - `check-feishu-cli.sh`
  - `check-feishu-cli-auth.sh`
  - `auth-feishu-cli.sh`
- `.github/workflows/`：仓库内默认工作流（CI 仅做环境与文档可用性检查）

## 关联命令

- `npm run feishu:install`
  - 执行 `npx @larksuite/cli@latest install`
- `npm run feishu:config`
  - 执行 `lark-cli config init --new`
- `npm run feishu:auth`
  - 执行 `lark-cli auth login --recommend`
- `npm run feishu:auth:proxyless`
  - 在强代理环境下执行鉴权（自动禁用 ALL_PROXY/HTTP(S)_PROXY）
- `npm run feishu:auth:device`
  - 执行 `lark-cli auth login --recommend --no-wait`
- `npm run feishu:auth:device:proxyless`
  - 在强代理环境下执行非阻塞鉴权，并返回授权流程信息
- `npm run feishu:status`
  - 执行 `lark-cli auth status`
- `npm run feishu:check`
  - 执行本地环境与文件完整性检查
- `npm run feishu:check:auth`
  - 只检查飞书授权是否完成
- `npm run feishu:check:full`
  - 同时执行本地检查与授权检查
- `npm run feishu:setup`
  - 执行 `scripts/setup-feishu-cli.sh`

## 注意事项

- `lark-cli auth login` 需要用户在浏览器中完成授权；在非交互环境请使用 `--device-code` 等参数。
- 不要将 App Secret、Token 等敏感信息提交到仓库。
