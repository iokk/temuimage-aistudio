#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-}"
WEB_BASE_URL="${WEB_BASE_URL:-}"

usage() {
  cat <<'EOF'
用法:
  API_BASE_URL=https://api.example.com WEB_BASE_URL=https://web.example.com ./scripts/zeabur_rebuild_release.sh

说明:
  1. 校验 Prisma schema
  2. 执行数据库部署脚本
  3. 运行发布 smoke checks
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$API_BASE_URL" || -z "$WEB_BASE_URL" ]]; then
  echo "❌ 请设置 API_BASE_URL 和 WEB_BASE_URL"
  usage
  exit 1
fi

echo "🔎 校验 Prisma schema..."
pnpm prisma:validate

echo "🗃️ 部署数据库迁移与 system seed..."
pnpm deploy:db

echo "🚦 执行 Zeabur 发布 smoke checks..."
python3 scripts/rebuild_release_smoke.py --api-base "$API_BASE_URL" --web-base "$WEB_BASE_URL" --require-ready

echo "✅ Zeabur Rebuild V1 发布检查通过"
