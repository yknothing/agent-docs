#!/usr/bin/env bash
set -euo pipefail

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 lark-cli。请先执行 npm run feishu:install。"
  exit 1
fi

# 默认请求推荐最小权限；如需自定义可传入 --scope/--domain/--no-wait 等参数。
AUTH_ARGS=("$@")
if [ ${#AUTH_ARGS[@]} -eq 0 ]; then
  AUTH_ARGS=("--recommend")
fi

# 关闭代理并跳过代理告警，避免凭据经由 socks/http 代理传输
set +e
OUTPUT=$(LARK_CLI_NO_PROXY=1 ALL_PROXY= all_proxy= HTTPS_PROXY= HTTP_PROXY= https_proxy= http_proxy= NO_PROXY= lark-cli auth login "${AUTH_ARGS[@]}" 2>&1)
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
  printf '%s\n' "$OUTPUT"

  if printf '%s\n' "$OUTPUT" | grep -q "No permission to access"; then
    cat <<'MSG'

[ERROR] 当前登录的飞书账号没有 CLI 访问权限。
建议按以下顺序处理：
1) 在浏览器确认账号是否为企业/组织账号，个人号（如 Feishu Personal User）通常不具备飞书 CLI 访问权限
2) 执行 lark-cli auth logout 清理当前登录态
3) 使用有权账号重新执行授权（可直接运行）
   LARK_CLI_NO_PROXY=1 ALL_PROXY= HTTPS_PROXY= HTTP_PROXY= lark-cli auth login --recommend --domain all
4) 如仍报错，请与企业管理员确认“应用权限审批/组织内应用允许列表”
MSG
  else
    echo "[ERROR] 鉴权失败。可尝试关闭代理后重试："
    echo "LARK_CLI_NO_PROXY=1 ALL_PROXY= HTTPS_PROXY= HTTP_PROXY= lark-cli auth login ${AUTH_ARGS[*]}"
    echo "    （如有 https/http 全小写环境变量，请先一并清空）"
  fi
  exit $EXIT_CODE
fi

printf '%s\n' "$OUTPUT"
echo "[OK] 鉴权完成。"
