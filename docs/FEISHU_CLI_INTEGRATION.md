# 飞书 CLI 接入说明

## 1. 安装

```bash
npx @larksuite/cli@latest install
```

该命令会根据环境要求安装 `lark-cli` 二进制并初始化技能能力。

## 2. 机器可用性检查

推荐先执行：

```bash
npm run feishu:check
```

脚本会检查以下项目：

1. `node` / `npm` 是否可用
2. `lark-cli` 命令是否可调用
3. 当前是否已完成飞书登录态（`lark-cli auth status`）

## 3. AI Assistant 模式（非阻塞授权）

如文档中说明，AI 使用场景可按以下方式执行，便于将认证链接返回给用户：

```bash
lark-cli config init --new
lark-cli auth login --recommend --no-wait
```

拿到授权链接并在用户浏览器完成授权后，回填 device code 恢复。

## 4. 常用命令示例

- 查看日历议程
  - `lark-cli calendar +agenda`
- 发送群聊消息
  - `lark-cli im +messages-send --chat-id "oc_xxx" --text "Hello"`
- 查看文档状态（需先完成鉴权）
  - `lark-cli auth status`

## 5. 安全边界

本仓库仅提供接入脚本与文档，敏感凭据应使用系统密钥链或环境变量托管；不要提交 `config.json`、Token、`client_secret` 等密钥内容。
