#!/bin/bash
set -euo pipefail

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "❌ 未检测到 docker compose / docker-compose"
  echo "请先安装 Docker Desktop 或 Docker Engine + Compose"
  exit 1
fi

case "${1:-up}" in
  up)
    [ -f .env ] || cp .env.example .env
    mkdir -p data data/files
    if ! grep -Eq '^(GOOGLE_API_KEY|GEMINI_API_KEY)=.+$' .env; then
      echo "⚠️  .env 未配置 GOOGLE_API_KEY / GEMINI_API_KEY，启动后可能无法调用模型"
    fi
    $DC up -d --build
    echo "✅ 服务已启动: http://localhost:8501"
    if $DC ps >/dev/null 2>&1; then
      $DC ps
    fi
    ;;
  down)
    $DC down
    ;;
  restart)
    $DC restart
    ;;
  logs)
    $DC logs -f
    ;;
  status)
    $DC ps
    if $DC ps | grep -q "temu-app"; then
      echo "ℹ️ 健康检查: http://localhost:8501/_stcore/health"
    fi
    ;;
  update)
    $DC down
    $DC up -d --build
    ;;
  clean)
    $DC down --rmi local
    ;;
  *)
    echo "用法: ./scripts/deploy-quick.sh [up|down|restart|logs|status|update|clean]"
    exit 1
    ;;
esac
