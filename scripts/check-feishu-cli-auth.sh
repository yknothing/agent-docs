#!/usr/bin/env bash
set -euo pipefail

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 lark-cli。请先执行 npm run feishu:install。"
  exit 1
fi

if ! OUTPUT=$(lark-cli auth status 2>&1); then
  echo "$OUTPUT"
  echo "[ERROR] 飞书 CLI 不可用或未配置。请执行: npm run feishu:install && npm run feishu:config"
  exit 2
fi

echo "$OUTPUT"

USER_LOGGED_IN=1
if echo "$OUTPUT" | grep -q 'No user logged in'; then
  USER_LOGGED_IN=0
fi

if [ "$USER_LOGGED_IN" -eq 1 ]; then
  echo "[OK] 飞书授权通过（auth_level=user）。"
  exit 0
fi

if echo "$OUTPUT" | grep -q '"identity": "bot"'; then
  echo "[OK] 飞书应用已配置（auth_level=bot）。"
  echo "[INFO] 当前无用户登录态。文档同步等用户态 API 请先执行: npm run feishu:auth"
  echo "[INFO] 个人账号与企业账号均可授权；勿将 No permission 误判为账号类型问题。"
  exit 0
fi

echo "[ERROR] 无法识别授权状态。请执行 npm run feishu:config && npm run feishu:auth"
exit 2
