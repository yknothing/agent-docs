#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 node。" >&2
  exit 1
fi

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 lark-cli。请先执行: npm run feishu:install" >&2
  exit 1
fi

if ! lark-cli auth status >/dev/null 2>&1; then
  echo "[ERROR] lark-cli 未完成授权。请执行: npm run feishu:auth" >&2
  exit 2
fi

echo "[OK] 飞书 CLI 已安装且已授权。"
