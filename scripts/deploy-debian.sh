#!/usr/bin/env bash
# ==================== TEMU 电商智能作图系统 Debian12+ 部署脚本 ====================
set -euo pipefail

APP_PORT="${APP_PORT:-8501}"
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      SUDO="sudo"
    else
      echo -e "${RED}需要 root 权限（无 sudo）${NC}"
      exit 1
    fi
  else
    SUDO=""
  fi
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  else
    DOCKER_COMPOSE=""
  fi
}

install_docker() {
  echo -e "${YELLOW}[1/5] 安装 Docker（Debian 12+）...${NC}"
  need_root
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | $SUDO sh
  fi
  $SUDO systemctl enable --now docker
  if ! docker compose version >/dev/null 2>&1; then
    $SUDO apt-get update -y
    $SUDO apt-get install -y docker-compose-plugin
  fi
  if [ -n "${SUDO}" ]; then
    $SUDO usermod -aG docker "${USER}" || true
    echo -e "${YELLOW}提示: 重新登录后 docker 免 sudo 生效${NC}"
  fi
}

prepare_env() {
  echo -e "${YELLOW}[2/5] 准备环境配置...${NC}"
  cd "$WORKDIR"
  if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✅ 已创建 .env 配置文件${NC}"
  fi
  mkdir -p data data/files
  echo -e "${GREEN}✅ 数据目录已创建${NC}"
}

build_image() {
  echo -e "${YELLOW}[3/5] 构建镜像...${NC}"
  $DOCKER_COMPOSE -f docker-compose.yml build --no-cache
  echo -e "${GREEN}✅ 镜像构建完成${NC}"
}

start_service() {
  echo -e "${YELLOW}[4/5] 启动服务...${NC}"
  $DOCKER_COMPOSE -f docker-compose.yml up -d
  echo -e "${GREEN}✅ 服务已启动${NC}"
}

show_status() {
  echo -e "${YELLOW}[5/5] 检查服务状态...${NC}"
  sleep 3
  if $DOCKER_COMPOSE -f docker-compose.yml ps | grep -q "Up\|running"; then
    echo -e "${GREEN}"
    echo "访问地址: http://<SERVER_IP>:${APP_PORT}"
    echo "默认密码:"
    echo "  用户密码: eee666"
    echo "  管理员密码: joolhome@2023"
    echo -e "${NC}"
  else
    echo -e "${RED}❌ 服务启动失败，请检查日志: ${DOCKER_COMPOSE} logs${NC}"
    exit 1
  fi
}

show_help() {
  echo "使用方法: ./scripts/deploy-debian.sh [install|start|stop|restart|logs|status|update|clean]"
}

detect_compose
if [ -z "${DOCKER_COMPOSE}" ]; then
  install_docker
  detect_compose
fi

case "${1:-install}" in
  install)
    install_docker
    prepare_env
    build_image
    start_service
    show_status
    ;;
  start)
    $DOCKER_COMPOSE -f docker-compose.yml up -d
    ;;
  stop)
    $DOCKER_COMPOSE -f docker-compose.yml down
    ;;
  restart)
    $DOCKER_COMPOSE -f docker-compose.yml restart
    ;;
  logs)
    $DOCKER_COMPOSE -f docker-compose.yml logs -f
    ;;
  status)
    $DOCKER_COMPOSE -f docker-compose.yml ps
    ;;
  update)
    $DOCKER_COMPOSE -f docker-compose.yml down
    $DOCKER_COMPOSE -f docker-compose.yml build --no-cache
    $DOCKER_COMPOSE -f docker-compose.yml up -d
    ;;
  clean)
    $DOCKER_COMPOSE -f docker-compose.yml down --rmi local
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    show_help
    exit 1
    ;;
esac
