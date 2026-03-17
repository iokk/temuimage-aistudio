#!/bin/bash
# ==================== TEMU 电商智能作图系统 V15.3.0 部署脚本 ====================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检测 docker compose 命令（新版用空格，旧版用连字符）
DOCKER_COMPOSE=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       🍌 TEMU 电商智能作图系统 V15.3.0 部署脚本            ║"
echo "║                                                              ║"
echo "║       核心作者: 企鹅 & 小明                                  ║"
echo "║       商业订阅: 企鹅 & Jerry                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检查 Docker
check_docker() {
    echo -e "${YELLOW}[1/5] 检查 Docker 环境...${NC}"
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker 未安装${NC}"
        echo -e "${YELLOW}是否自动安装 Docker? (y/n)${NC}"
        read -r install_docker
        if [ "$install_docker" = "y" ]; then
            echo -e "${BLUE}正在安装 Docker...${NC}"
            curl -fsSL https://get.docker.com | sh
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            echo -e "${GREEN}✅ Docker 安装完成${NC}"
        else
            echo -e "${RED}请手动安装 Docker 后重试${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Docker 已安装: $(docker --version)${NC}"
    fi

    echo -e "${GREEN}✅ 使用命令: ${DOCKER_COMPOSE}${NC}"
}

# 准备环境
prepare_env() {
    echo -e "${YELLOW}[2/5] 准备环境配置...${NC}"
    
    if [ ! -f .env ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ 已创建 .env 配置文件${NC}"
        echo -e "${YELLOW}提示: 可以编辑 .env 文件配置 API Key，或在管理后台初始化${NC}"
    else
        echo -e "${GREEN}✅ .env 配置文件已存在${NC}"
    fi
    
    # 创建数据目录
    mkdir -p data data/files
    echo -e "${GREEN}✅ 数据目录已创建${NC}"
}

# 构建镜像
build_image() {
    echo -e "${YELLOW}[3/5] 构建 Docker 镜像...${NC}"
    $DOCKER_COMPOSE build --no-cache
    echo -e "${GREEN}✅ 镜像构建完成${NC}"
}

# 启动服务
start_service() {
    echo -e "${YELLOW}[4/5] 启动服务...${NC}"
    $DOCKER_COMPOSE up -d
    echo -e "${GREEN}✅ 服务已启动${NC}"
}

# 显示状态
show_status() {
    echo -e "${YELLOW}[5/5] 检查服务状态...${NC}"
    sleep 5
    
    if $DOCKER_COMPOSE ps | grep -q "Up\|running"; then
        echo -e "${GREEN}"
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                    🎉 部署成功！                             ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║                                                              ║"
        echo "║  访问地址: http://localhost:8501                             ║"
        echo "║  或: http://$(hostname -I | awk '{print $1}'):8501           ║"
        echo "║                                                              ║"
        echo "║  默认密码:                                                   ║"
        echo "║    用户密码: eee666                                          ║"
        echo "║    管理员密码: joolhome@2023                                 ║"
        echo "║                                                              ║"
        echo "║  首次使用请在管理后台配置 API Key 或使用自己的 Key           ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
    else
        echo -e "${RED}❌ 服务启动失败，请检查日志: ${DOCKER_COMPOSE} logs${NC}"
        exit 1
    fi
}

# 显示帮助
show_help() {
    echo "使用方法: ./deploy.sh [命令]"
    echo ""
    echo "命令:"
    echo "  install   - 完整安装部署（默认）"
    echo "  start     - 启动服务"
    echo "  stop      - 停止服务"
    echo "  restart   - 重启服务"
    echo "  logs      - 查看日志"
    echo "  update    - 更新并重启"
    echo "  status    - 查看状态"
    echo "  clean     - 清理（保留数据）"
    echo "  help      - 显示帮助"
}

# 主流程
case "${1:-install}" in
    install)
        check_docker
        prepare_env
        build_image
        start_service
        show_status
        ;;
    start)
        $DOCKER_COMPOSE up -d
        echo -e "${GREEN}✅ 服务已启动${NC}"
        ;;
    stop)
        $DOCKER_COMPOSE down
        echo -e "${GREEN}✅ 服务已停止${NC}"
        ;;
    restart)
        $DOCKER_COMPOSE restart
        echo -e "${GREEN}✅ 服务已重启${NC}"
        ;;
    logs)
        $DOCKER_COMPOSE logs -f
        ;;
    update)
        $DOCKER_COMPOSE down
        $DOCKER_COMPOSE build --no-cache
        $DOCKER_COMPOSE up -d
        echo -e "${GREEN}✅ 更新完成${NC}"
        ;;
    status)
        $DOCKER_COMPOSE ps
        ;;
    clean)
        $DOCKER_COMPOSE down --rmi local
        echo -e "${GREEN}✅ 清理完成（数据已保留）${NC}"
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
