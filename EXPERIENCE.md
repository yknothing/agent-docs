# EXPERIENCE.md

本仓库的经验沉淀：**踩坑、决策、限制**。Agent 解决新问题后应追加一条记录。

## 如何使用

- **读**：遇到奇怪失败前先扫一眼近期条目。
- **写**：问题解决后追加，格式见下方模板。
- **不删**：过时条目标 `[ superseded ]`，保留上下文。

## 记录模板

```markdown
### YYYY-MM-DD — 简短标题

**上下文**：用户在做什么 / 改了什么
**现象**：报错或异常行为（可贴 error 码）
**根因**：一句话
**解法**：可执行步骤或 PR 链接
**预防**：以后 Agent 应如何避免
```

---

## 已沉淀经验

### 2026-05-22 — /goal Phase 0-4 验证被环境变量阻塞

**上下文**：执行 `docs/CODEX_GOAL.md` 验收链路，要求跑到 Phase 4 并产出 `feishu_sync_report` PASS。
**现象**：Phase 4 `--execute-feishu` 返回 `overall_status: FAIL`，`batch_qa_report.json` 记录 `feishu_sync_FAIL: FEISHU_DOC_FOLDER_TOKEN missing`，`pipeline.log` 打印 `error_code: feishu_token_missing`。
**根因**：会话未设置 `FEISHU_DOC_FOLDER_TOKEN`（需指向云盘上 `agent-docs` 文件夹 token）；执行环境无法进入真实上传。
**解法**：确认并设置 `FEISHU_DOC_FOLDER_TOKEN` 后，使用同一 `output_root` 重跑 execute（需先保留 dry-run 产物核对 `folder_path`）。
**预防**：在所有涉及 `--execute-feishu` 的操作前，用 `npm run feishu:check:full` 与 `scripts/anthropic_content_pipeline.py --self-test-feishu-paths` 验证后再执行；必要时在 `DEBUG.md` 的 auth/token 检查项后附上当前 token 获取步骤。

### [superseded] 2026-05 — 飞书个人账号无法授权 CLI

**上下文**：首次 `npm run feishu:auth`
**现象**：`No permission to access`，账号显示 `Feishu Personal User`
**原结论（错误）**：个人账号通常不可用 — **已被实测否定**
**修正**：见下条「个人账号可接入 CLI」

---

### 2026-05-21 — 个人账号可接入飞书 CLI

**上下文**：仓库接入与文档交叉评审；用户已完成个人账号接入
**现象**：历史文档/脚本将 `No permission` + `Feishu Personal User` 误判为账号类型不支持
**根因**：`No permission` 多由代理、过期会话、未完成 OAuth、企业应用审批导致；Personal User 仅为身份标签
**解法**：`lark-cli auth logout` → `npm run feishu:auth:device:proxyless` → 浏览器完成授权 → `npm run feishu:check:full`
**预防**：鉴权失败先查代理与会话，不要建议“换企业号”；见 `docs/FEISHU_CLI_INTEGRATION.md` §4.1–4.2
**验证**（2026-05-21）：`npm run feishu:check:full` 通过；`auth status` 显示 `appId` + bot 就绪；`lark-cli doctor`  endpoint 可达（user token 视会话而定）

---

### 2026-05 — 代理导致飞书 OAuth 失败

**上下文**：本机设了 `ALL_PROXY` / Clash 等
**现象**：登录卡住、token 交换失败
**根因**：OAuth 流量被错误转发
**解法**：`LARK_CLI_NO_PROXY=1` 或 `npm run feishu:auth:device:proxyless`
**预防**：飞书相关命令优先 proxyless 变体；`auth-feishu-cli.sh` 已支持该模式

---

### 2026-05 — 流水线拒绝写入已有 batch 目录

**上下文**：第二次全量 crawl 同一 `output-root`
**现象**：`overall_status: FAIL`，errors 含 `output_root already contains batch directories`
**根因**：故意防止旧 batch 与新 run 混合
**解法**：新目录 `--output-root artifacts/anthropic-content-2`，或 `--resume-output` 续跑
**预防**：Agent 不要默认删 batch；续跑必须显式 flag

---

### 2026-05 — 全量 crawl 前必须先 smoke

**上下文**：修改 `anthropic_content_pipeline.py` 后直接全量
**现象**：长时间运行后整批 QA FAIL（翻译/API/结构问题）
**根因**：smoke 成本低，能提前暴露抓取或翻译回归
**解法**：固定顺序 discover → `anthropic:crawl:smoke` → 全量 crawl
**预防**：见 `AGENTS.md` 推荐工作流；改 QA/翻译/抓取逻辑后必跑 smoke

---

### 2026-05 — 飞书同步不等于 dry-run 成功

**上下文**：跑 `anthropic:sync-dryrun` 后以为已上传
**现象**：飞书侧无文档
**根因**：dry-run 只写 `feishu_sync_commands.sh`，不调用 API
**解法**：确认 QA PASS + token + auth 后跑 `anthropic:sync`（含 `--execute-feishu`）
**预防**：向用户说明 DRY_RUN vs EXECUTE；见 `ARCHITECTURE.md` sync 状态机

---

### 2026-05 — QA 阻断中文缺失

**上下文**：未配置 `LANGCRAFT_CMD` / `OPENAI_API_KEY` 跑全量+QA
**现象**：大量 `translate_missing` / `zh_output_language_check_failed`
**根因**：流水线中文优先，无翻译器时无法产出合格 `final.zh.md`
**解法**：配置翻译器，或对验证性运行使用 `--translate-mode off` + `--no-qa`（仅 smoke）
**预防**：全量生产路径必须配置翻译；smoke 默认已关翻译和 QA

---

### 2026-05 — CI 不验证飞书登录

**上下文**：CI 绿但本地 sync 失败
**现象**：`feishu:check` 通过，`feishu:check:auth` 失败
**根因**：`.github/workflows/feishu-cli-smoke.yml` 刻意不要求 auth，便于无交互 CI
**解法**：本地/发布前单独跑 `feishu:check:full`
**预防**：Agent 不要假设 CI 覆盖了鉴权；见 `AGENTS.md` CI 边界

---

### 2026-05-21 — `docs +create --content` 产出空文档（假成功）

**上下文**：E2E 飞书 sync 报 PASS，但云盘目录为空或文档无正文
**现象**：`lark-cli docs +create` 返回 `ok: true`，但带 `degrade_code=1011`（Instruction produced no document changes）；`docs +fetch` 仅见 Untitled + 图片块
**根因**：v2 下 `docs +create --content @file` 不可靠；`drive +import` 才是正文导入正确路径
**解法**：`sync_to_feishu` 改用 `drive +import --type docx`；同步后 `docs +fetch` 校验 `content_length >= 200`
**预防**：禁止回退到 `docs +create` 作为主路径；见 `ARCHITECTURE.md` §2.6

---

### 2026-05-21 — 飞书目录层级与 `FEISHU_DOC_FOLDER_TOKEN` 含义混淆

**上下文**：测试用 `agent-docs-e2e-real` 作 token 根，用户期望 `agent-docs/anthropic-docs/…`
**现象**：UI 中多出一层测试目录名，或与预期 `agent-docs/` 根不一致
**根因**：`FEISHU_DOC_FOLDER_TOKEN` 应指向 **`agent-docs` 文件夹**（`FEISHU_DOC_ROOT_MODE=agent-docs-folder`，默认），其下才是 `anthropic-docs/Anthropic/…`；勿用临时 e2e 目录名作生产根
**解法**：
  ```bash
  lark-cli drive +create-folder --name agent-docs
  export FEISHU_DOC_FOLDER_TOKEN='<token>'
  export FEISHU_DOC_ROOT_MODE=agent-docs-folder   # 默认
  ```
  若 token 指向云盘根目录，则设 `FEISHU_DOC_ROOT_MODE=parent`，流水线会创建 `agent-docs/` 再建子目录
**预防**：E2E 与生产使用同一命名约定；见 `AGENTS.md` 飞书目录规范

---

### 2026-05-21 — 重复创建同名 folder

**上下文**：多次 sync 后在同一父目录出现多个 `anthropic-content` / `anthropic-docs`
**现象**：飞书 UI 中并列多个同名文件夹
**根因**：`drive +create-folder` 不幂等，每次调用都新建；batch 级 cache 无法跨 run 复用
**解法**：使用 `{output_root}/.feishu_folder_cache.json`，键为 `parent_token::folder_name` 与完整路径键
**预防**：删 cache 前确认是否要重建目录；不要手动重复跑 create-folder

---

### 2026-05-21 — 图片下载 30s 超时导致 QA FAIL

**上下文**：`platform.claude.com` 大图（500KB+）抓取
**现象**：`image_download_failed`；curl 需 65–140s
**根因**：`fetch_bytes` 默认 timeout=30
**解法**：`DEFAULT_IMAGE_FETCH_TIMEOUT=180`
**预防**：改超时后跑 `anthropic:crawl:smoke` 验证含图页面

---

### 2026-05-21 — import 正文含 `media/` 链接导致飞书图片占位失败

**上下文**：`drive +import` 导入含 `![](media/xxx.png)` 的 markdown
**现象**：飞书显示「无法导入该图片」灰色占位
**根因**：import 无法解析本地 `media/` 路径
**解法**：`sanitize_feishu_import_markdown` 去掉图片 markdown，改为 `**[图] alt**` 占位；正文 import 后用 `docs +media-insert` 追加（带 `--caption`），不用 `--selection-with-ellipsis`
**预防**：sync 报告检查 `expected_images` 与 `verification.image_count`

---

### 2026-05-21 — `lark-cli` JSON 解析失败（stderr 污染）

**上下文**：`ensure_feishu_folder` 报 RuntimeError 但 rc=0
**现象**：`parse_lark_cli_json` 返回 None
**根因**：stdout JSON 后追加 stderr（Creating folder…），`json.loads` 整体解析失败
**解法**：`json.JSONDecoder().raw_decode(text[start:])` 只解析首个 JSON 对象
**预防**：所有 `parse_lark_cli_json` 调用统一用 raw_decode

---

### 2026-05-21 — subprocess 中 `@file` 路径无效

**上下文**：Python `subprocess.run([..., "--file", "@batch/..."])` 调 import
**现象**：exit 2，validation 失败
**根因**：`@` 前缀仅 shell 脚本约定，subprocess 列表需传相对路径字符串
**解法**：`--file batch-001/sync_payload/xxx.feishu.md`（无 `@`）
**预防**：dry-run 脚本可保留 `@`；Python 直调不可

---

### 2026-05-22 — 多厂商资料库定位与 `folder_path` 完整路径

**上下文**：用户纠正目录结构后，文档仍按 Anthropic 单源描述；E2E 清单 `folder_path` 缺少 `agent-docs/` 前缀，与 UI 逐级展开不一致。

**修复**：
- 仓库定位扩展为多厂商资料库（`anthropic-docs` active；`openai-docs` / `gemini-docs` / `cursor-docs` reserved）
- 代码：`VENDOR_LIBRARIES` + `feishu_full_folder_path()`；sync report 的 `folder_path` 含 `agent-docs/` 前缀
- 文档：`AGENTS.md`、`ARCHITECTURE.md`、`DEBUG.md`、`CODEX_GOAL.md` 对齐

**验收**：`python3 scripts/anthropic_content_pipeline.py --self-test-feishu-paths`

---

### 2026-05-22 — pipeline.log 结构化日志

**上下文**：Goal 要求仅凭 WARN/ERROR/进度日志即可定位并重试失败项。

**实现**：`PipelineLogger` 写入 `{output_root}/pipeline.log`（JSON Lines）；`run_pipeline` / `process_target` / `run_qa` / `sync_to_feishu` 关键路径已接入。

**排障**：`grep '"level": "ERROR"' artifacts/.../pipeline.log` 或按 `error_code` 过滤；对照同 batch 的 `batch_qa_report.json`。

---

### 2026-05-22 — 飞书目录总纲 upsert 与 fallback

**上下文**：Phase 2 目录索引 `sync_feishu_folder_indexes`；re-sync 同一飞书文件夹
**现象**：首次 sync 创建 `📋 目录总纲`；再次 sync 需更新表格而非重复建 doc
**根因**：`lark-cli docs +update` 可用性因 CLI/API 版本而异；无稳定 update 时需 fallback
**解法**：`.feishu_index_cache.json` 按 `folder_token → doc_id` 缓存；execute 时优先 `docs +update --mode overwrite`；失败则 WARN 并 fallback 到 `drive +import` 同名 doc，成功后刷新 cache。dry-run 在 `feishu_sync_commands.sh` 写入对应 update 或 import 命令
**预防**：改 `feishu_folder_segments` 后清 `.feishu_index_cache.json`；验收看 `feishu_sync_report.json` 的 `folder_indexes[]` 与 `feishu_folder_index.json`
**限制**：fallback re-import 可能在飞书侧产生同名重复 doc（旧 doc 需手动删）；长期依赖 `docs +update` 成功路径

---

## 决策记录（Durable）

| 决策 | 原因 |
|------|------|
| 仓库 = 多厂商资料库（`VENDOR_LIBRARIES`） | Anthropic active；OpenAI/Gemini/Cursor 预留同级 `{vendor}-docs/` |
| `folder_path` = 云盘根起完整路径（含 `agent-docs/`） | 与飞书 UI 逐级展开一致；`folder_segments` 不含该前缀 |
| `FEISHU_DOC_FOLDER_TOKEN` → 文件夹名 `agent-docs` | 厂商库在其下；勿用 e2e 临时目录作生产根 |
| 同步策略 = `drive +import` + `media-insert` | `docs +create` 空文档风险 |
| 目录 = URL 映射 + `feishu_folder_segments` | 与 Anthropic 信息架构一致，可维护 |
| 术语保留 Agent/Skill/Token + LangCraft 优先 | 用户要求；见 `AGENTS.md` 翻译节 |
| Courses 不同步 | 视频为主；正文视频保留 URL 不嵌入 |
| QA PASS 才 sync（默认） | 防止脏数据进飞书 |
| 同步后 fetch 校验 | 避免假 PASS |
| 目录总纲 = `📋 目录总纲` + index cache | 飞书非 git；按 folder upsert；机器层 `feishu_folder_index.json` |

---

### 2026-05-22 — 飞书目录总纲 upsert 策略

**上下文**：Phase 2 目录级索引；每个飞书文件夹需一篇 `📋 目录总纲`
**现象**：re-sync 若重复 `drive +import` 会创建多篇同名索引
**根因**：飞书无「按标题 upsert」API；需本地 cache 记录 index doc_id
**解法**：`.feishu_index_cache.json` 映射 `folder_token → doc_id`；execute 时优先 `lark-cli docs +update --api-version v2 --mode overwrite`；update 失败则 fallback re-import 并刷新 cache
**预防**：dry-run 检查 `feishu_sync_commands.sh` 末尾是 `+update`（有 cache）还是 `+import`（首次）；机器可读索引见 `{output_root}/feishu_folder_index.json`

---

## 待观察 / 开放问题

<!-- 在此追加尚未完全验证的假设，验证后移到上方「已沉淀经验」 -->

- Anthropic 源站结构变更时，需更新 `fetch_url` / markdown 解析逻辑（尚无固定监测手段，依赖 QA 计数下降报警）

---

### 2026-05-26 — P0 hardening pass（packaging + tests + secret scrubbing）

**上下文**：外部代码 review 指出 0 测试、无 LICENSE、无 pyproject.toml、`_sanitize` 仅过滤 dict key 不扫描 value、ARCHITECTURE.md 描述已不存在的"1300+ 行单文件"等问题。

**实施**（P0 hardening，**未改 crawl/QA/Feishu sync 主逻辑**；有意的运行时差异见下方第 5–7 点）：

1. 加 `LICENSE`（MIT + 非商业内容免责声明）。
2. 加 `pyproject.toml`：声明 `requires-python>=3.10`、`console_scripts`、`pytest`/`ruff` dev extras；引入 ruff 配置（当前 `E/F/W` only，避免 UP/B/SIM 大面积 churn）。
3. 加 `tests/` 单测（约 86 passed + 1 xfailed），覆盖 `feishu_folder_segments`（URL → 文件夹段映射，含 parent/agent-docs-folder 两种模式 + 所有 vendor 分支）、`parse_doc_id_from_output`（lark-cli 输出解析的 6 种形态）、`parse_frontmatter`（已支持 + xfail 标记的已知限制）、`feishu_safe_name`、`pick_preferred_source_url`（mock 网络）、`extract_images`、`PipelineLogger` secret 脱敏。
4. 加 `.github/workflows/python-ci.yml`：`ruff` + `py_compile` + `pytest` + `--self-test-feishu-paths`，Python 3.10 / 3.12 matrix。
5. 强化 `PipelineLogger._sanitize`：除了过滤 dict key 名外，新增对 string value 的高置信度 secret 扫描（Bearer、`sk-`/`sk-ant-`、GitHub PAT、`cli_*` 飞书 app secret、URL credential 查询参、`authorization=`/`x-api-key=`/`app_secret=` 字面赋值）。**故意不做"长随机串"启发式**，以免误伤 `folder_token` / `doc_id` / `sha1` 等正常 debug 字段。
6. `UA` header 改为 `agent-docs/0.1 (+https://github.com/yknothing/agent-docs)`，遵循"identify-yourself"礼节；减少被 WAF 误判风险。
7. 删除死代码：`FEISHU_ALT_TEXT_MIN_LEN` / `FEISHU_ALT_TEXT_HINT_MAX_LEN`（未引用）、`agent_docs/__init__.py` 自动调用的 `sys.path` hack（脚本 wrapper 仍有；preferred `pip install -e .`）、`extract_images` 中 dead `seen` 变量与多余 dedup 循环、`normalize.py` 未用 `from pathlib import Path`。
8. ARCHITECTURE.md：移除"约 1300+ 行"过时表述，扩展点表更新为 `agent_docs.*` 模块路径，新增 "Known Limitations" 节集中列出 8 项已识别但本轮不修复的限制。
9. README.md：重排 Quick Start，把 "Stage 1 主线"（`anthropic:discover` → `crawl:smoke` → `crawl`）置于飞书安装之前；加非商业使用 disclaimer。
10. 加 `skills/vendor-onboarding/SKILL.md` 作为 Stage 2 placeholder，消除"被引用但不存在"的死引用。
11. 加 `CHANGELOG.md`（Keep-a-Changelog 格式）。

**验证**：

```bash
pip install -e ".[dev]"
python -m ruff check .                            # All checks passed
npm run test:py                                   # 86 passed, 1 xfailed
python -m pytest tests/ -ra                       # same
python -m py_compile scripts/anthropic_content_pipeline.py
python -m compileall -q agent_docs
python scripts/anthropic_content_pipeline.py --self-test-feishu-paths   # [OK]
npm run anthropic:crawl:smoke                                         # exit 0（新 UA 下 5 条抓取正常）
```

**未做**（留给下一轮）：

- 拆分 `agent_docs/sinks/feishu.py`（1197 行 → 5 个文件）
- 用 `markdown-it-py + beautifulsoup4` 替换正则 HTML/MD 解析
- vendor 配置数据化（解硬编码 `feishu_folder_segments` 中的 vendor 分支）
- QA v2：源 HTML 解析 vs final markdown 跨格式比对

**预防**：

- 之后任何对 `feishu_folder_segments` / `parse_doc_id_from_output` / `PipelineLogger` / `extract_images` / `feishu_safe_name` 的修改，**必须先看 `tests/test_*.py` 对应文件，新加 case 后再改实现**。
- 改 secret 扫描规则要同步 `tests/test_pipeline_logger.py::TestValueScrubbing` 并保证不误伤现有 INFO 日志样本。
