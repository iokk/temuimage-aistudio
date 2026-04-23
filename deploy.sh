#!/usr/bin/env bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE="docker-compose"
else
  echo -e "${RED}未找到 Docker Compose，请先安装 Docker。${NC}"
  exit 1
fi

print_header() {
  echo -e "${BLUE}"
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║                     电商出图工作台部署脚本                  ║"
  echo "║                 self-hosted 单机版 / Linux                  ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

prepare_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}已创建 .env，请按需补充 API Key。${NC}"
  fi
  mkdir -p data data/files data/projects
}

build_image() {
  $DOCKER_COMPOSE build --no-cache
}

start_service() {
  $DOCKER_COMPOSE up -d
}

show_status() {
  sleep 5
  $DOCKER_COMPOSE ps
  echo
  echo -e "${GREEN}访问地址: http://localhost:${APP_PORT:-8501}${NC}"
  echo -e "${GREEN}健康检查: http://localhost:${APP_PORT:-8501}/_stcore/health${NC}"
  echo -e "${YELLOW}server 版结果会先保存到服务器项目中心，再由用户在浏览器中下载。${NC}"
}

show_help() {
  cat <<'EOF'
使用方法: ./deploy.sh [命令]

命令:
  install   完整部署
  start     启动服务
  stop      停止服务
  restart   重启服务
  logs      查看日志
  update    重新构建并启动
  status    查看状态
  clean     停止并删除本地镜像
  help      显示帮助
EOF
}

case "${1:-install}" in
  install)
    print_header
    prepare_env
    build_image
    start_service
    show_status
    ;;
  start)
    $DOCKER_COMPOSE up -d
    ;;
  stop)
    $DOCKER_COMPOSE down
    ;;
  restart)
    $DOCKER_COMPOSE restart
    ;;
  logs)
    $DOCKER_COMPOSE logs -f
    ;;
  update)
    print_header
    prepare_env
    $DOCKER_COMPOSE down
    build_image
    start_service
    show_status
    ;;
  status)
    $DOCKER_COMPOSE ps
    ;;
  clean)
    $DOCKER_COMPOSE down --rmi local
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    echo -e "${RED}未知命令: $1${NC}"
    show_help
    exit 1
    ;;
esac

