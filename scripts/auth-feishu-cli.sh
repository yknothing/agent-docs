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

[ERROR] 当前飞书账号未完成 CLI 授权（No permission to access）。
个人账号与企业账号均可接入；此报错通常不是“个人号不支持”，请按顺序排查：
1) 执行 lark-cli auth logout 清理过期/错误登录态
2) 禁用代理后重登: npm run feishu:auth:device:proxyless
3) 浏览器确认完成对 cli_* 应用的授权（含文档等所需 scope）
4) 若为企业租户，请管理员确认应用审批与组织内允许列表
5) 验证: npm run feishu:check:full && lark-cli doctor
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
