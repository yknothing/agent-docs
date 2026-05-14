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

## 4.1 授权失败排查（No permission）

你遇到的报错：

> No permission to access  
> The current account aicafe (Feishu Personal User) doesn't have permission for 飞书 CLI.

是账号权限问题，不是脚本本身问题。`aicafe` 是个人账号（Feishu Personal User），多数场景不具备 CLI 应用授权范围。

处理步骤（按顺序执行）：

1. 停掉当前登录态（防止继续复用错误账号）
   ```bash
   lark-cli auth logout
   ```
2. 用授权账号重登，禁用代理发起鉴权（避免 `ALL_PROXY` 把凭据走代理）
   ```bash
   npm run feishu:auth:device:proxyless
   ```
3. 按浏览器提示完成授权后，恢复并验证
   ```bash
   npm run feishu:check:full
   ```
4. 若仍失败，检查企业后台是否允许该账号接入飞书 CLI，并确认账号有企业身份或已加入目标租户。

临时可用状态命令：

```bash
lark-cli auth list         # 查看当前会话中已登录账号
lark-cli doctor            # 检查 CLI 配置与鉴权健康
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
- 诊断登录状态
  - `lark-cli auth list`
- 健康检查
  - `lark-cli doctor`

## 7. 安全边界

本仓库仅提供接入脚本与文档，请勿提交敏感信息。
建议将飞书授权凭据存储在系统安全存储或 CI 秘密管理中，禁止明文落盘。
