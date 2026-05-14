#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 node。请先安装 Node.js。"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 npm。请先安装 npm。"
  exit 1
fi

if command -v lark-cli >/dev/null 2>&1; then
  if ! lark-cli --version >/dev/null 2>&1; then
    echo "[ERROR] 检测到 lark-cli，但执行失败。"
    exit 1
  fi
  echo "[OK] lark-cli 可用。"
else
  echo "[WARN] 未检测到 lark-cli。请先执行 npm run feishu:install。"
fi

for file in scripts/setup-feishu-cli.sh scripts/check-feishu-cli-auth.sh scripts/check-feishu-cli.sh docs/FEISHU_CLI_INTEGRATION.md; do
  if [ ! -f "$file" ]; then
    echo "[ERROR] 缺少文件: $file"
    exit 1
  fi
done

echo "[OK] 飞书 CLI 仓库文件检查通过。"
