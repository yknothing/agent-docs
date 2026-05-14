#!/usr/bin/env bash
set -euo pipefail

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 lark-cli。请先执行 npm run feishu:install。"
  exit 1
fi

if ! lark-cli auth status; then
  echo "[ERROR] 飞书授权未完成。请执行: npm run feishu:auth"
  exit 2
fi

echo "[OK] 飞书授权通过。"
