# 飞书 CLI 接入说明

## 1. 安装

```bash
npx @larksuite/cli@latest install
```

该命令会根据环境要求安装 `lark-cli` 二进制并初始化技能能力。

> 说明：以下检查默认不要求 CI 环境先完成飞书登录态，便于无交互运行。

## 2. 机器可用性检查

推荐先执行：

```bash
npm run feishu:check
```

该命令会执行：

1. `node` / `npm` 是否可用
2. `lark-cli` 是否可调用（若未安装则给出提示）
3. 仓库接入文件是否存在且可用

## 3. 鉴权检查

完成授权后执行：

```bash
npm run feishu:check:auth
```

脚本会检查 `lark-cli auth status`，确认是否已完成登录。

## 4. 一键流程（推荐）

```bash
npm run feishu:setup      # 安装
npm run feishu:config     # 生成应用配置（交互）
npm run feishu:auth       # 登录（交互）
npm run feishu:check:auth  # 校验授权
```

## 5. AI Assistant 模式（非阻塞授权）

如果你要让 AI 侧先发起授权链接：

```bash
lark-cli config init --new
lark-cli auth login --recommend --no-wait
```

拿到链接后引导用户在浏览器完成授权，再按恢复流程执行。

## 6. 常用命令示例

- 查看日历议程
  - `lark-cli calendar +agenda`
- 发送群聊消息
  - `lark-cli im +messages-send --chat-id "oc_xxx" --text "Hello"`
- 查看授权状态
  - `lark-cli auth status`

## 7. 安全边界

本仓库仅提供接入脚本与文档，请勿提交敏感信息。
建议将飞书授权凭据存储在系统安全存储或 CI 秘密管理中，禁止明文落盘。
