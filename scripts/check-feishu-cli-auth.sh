#!/usr/bin/env bash
set -euo pipefail

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 lark-cli。请先执行 npm run feishu:install。"
  exit 1
fi

if ! OUTPUT=$(lark-cli auth status 2>&1); then
  echo "$OUTPUT"
  echo "[ERROR] 飞书授权未完成。请执行: npm run feishu:auth"
  exit 2
fi

if echo "$OUTPUT" | grep -q '"identity"'; then
  echo "$OUTPUT"
  if echo "$OUTPUT" | grep -q '"identity": "bot"'; then
    echo "[INFO] 当前仅有 bot 身份。若你要以个人账号权限发起命令，请先执行: npm run feishu:auth"
  fi
  echo "$OUTPUT" | grep -q '"note": "No user logged in' && echo "[INFO] 当前未登录用户身份，建议重新运行 npm run feishu:auth 进行用户授权。"
fi

echo "[OK] 飞书授权通过。"
