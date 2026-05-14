#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 node，请先安装 Node.js 后重试。" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 npm，请先安装 npm 后重试。" >&2
  exit 1
fi

echo "[INFO] 使用官方推荐方式安装飞书 CLI..."
npx @larksuite/cli@latest install

echo "[INFO] 安装完成。若为首次接入请继续执行："
echo "  lark-cli config init --new"
echo "  npm run feishu:auth"
