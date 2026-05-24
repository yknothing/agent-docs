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

## 4.1 身份模型（bot / user）

`lark-cli auth status` 可能呈现两种就绪级别：

| auth_level | 含义 | 典型场景 |
|------------|------|----------|
| `bot` | 应用已配置，仅有 bot/tenant 身份 | `config init` 完成，用户尚未 `auth login` |
| `user` | 用户已完成 OAuth 登录 | 文档创建、需用户态 scope 的 API |

**个人账号与企业账号均可完成 user 授权。** 勿将 `Feishu Personal User` 标签等同于“不可用”。

本仓库 `npm run feishu:check:auth` 在 `bot` 与 `user` 两种级别下均可通过，但会提示是否缺少用户登录态。

## 4.2 授权失败排查（No permission）

示例报错：

> No permission to access  
> The current account ... (Feishu Personal User) doesn't have permission for 飞书 CLI.

**常见根因**（按频率）：

1. **代理干扰 OAuth** — `ALL_PROXY` / Clash 等导致 token 交换失败
2. **过期或错误登录态** — 需 `lark-cli auth logout` 后重登
3. **浏览器未完成应用授权** — 未勾选/未确认 cli 应用 scope
4. **企业租户策略** — 应用未审批、账号不在允许列表（企业场景）

处理步骤（按顺序执行）：

1. 清理登录态
   ```bash
   lark-cli auth logout
   ```
2. 禁用代理重登
   ```bash
   npm run feishu:auth:device:proxyless
   ```
3. 浏览器完成授权后验证
   ```bash
   npm run feishu:check:full
   lark-cli auth list
   lark-cli doctor
   ```
4. 企业租户仍失败时，请管理员检查应用审批与组织策略。

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
