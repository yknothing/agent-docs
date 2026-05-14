# agent-docs

本仓库用于接入飞书 CLI（lark-cli），先做最小闭环：可复用脚本、配置说明与鉴权检查。

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

## 目录

- `docs/FEISHU_CLI_INTEGRATION.md`：接入说明（含 AI Assistant 模式步骤）
- `scripts/`：用于安装与接入的脚本
  - `setup-feishu-cli.sh`
  - `check-feishu-cli.sh`
  - `check-feishu-cli-auth.sh`
- `.github/workflows/`：仓库内默认工作流（CI 仅做环境与文档可用性检查）

## 关联命令

- `npm run feishu:install`
  - 执行 `npx @larksuite/cli@latest install`
- `npm run feishu:config`
  - 执行 `lark-cli config init --new`
- `npm run feishu:auth`
  - 执行 `lark-cli auth login --recommend`
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
